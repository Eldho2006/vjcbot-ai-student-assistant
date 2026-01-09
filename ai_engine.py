import os
import google.generativeai as genai

# Lightweight imports only
import os
import google.generativeai as genai

# RAG dependencies removed to save space (Vercel < 250MB limit)
# We now use Database + Simple Context Stuffing

class AIEngine:
    def __init__(self):
        # Initialize Google Gemini
        self.model = None
        try:
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                print("Warning: GOOGLE_API_KEY not set")
            else:
                genai.configure(api_key=api_key)
                # Use 1.5-flash (Stable) to avoid startup errors
                self.model = genai.GenerativeModel('gemini-1.5-flash')
        except Exception as e:
            print(f"FAILED TO INIT AI ENGINE: {e}")
            self.model = None
        
        # Removed Chroma/LangChain components

    def add_document(self, text, metadata):
        """Adds a document to the vector store (or file backup)."""
        # NOTE: For Vercel/DB-only mode, 'add_document' is largely symbolic 
        # because app.py handles the DB insertion. 
        # We can keep this for compatibility if we want to do extra processing.
        # But primarily, the 'get_answer' method reads from the DB.
        pass

    def get_answer(self, query):
        """
        Retrieves answer from Knowledge Base (DB) or Search.
        """
        context = "" # Initialize context outside
        
        # 1. Retrieve Local Context from DATABASE
        full_text = ""
        try:
            # Import here to avoid circular dependencies at module level if possible, 
            # strictly inside the function where standard app context is active.
            from database import Document
            
            # Retrieve all processed documents
            # Optimization: In a real large app, we would use Vector Search (pgvector)
            # But for this "Free Tier" request, we allow "Context Stuffing" of all text.
            docs = Document.query.filter(Document.content != None).all()
            full_text = "\n\n".join([d.content for d in docs if d.content])
            
        except Exception as db_e:
            print(f"Database Read Error: {db_e}")
            full_text = ""

        # --- HARD FILTER LOGIC ---
        # Parsing line-by-line to safely identify and exclude syllabus sections
        is_syllabus_query = any(k in query.lower() for k in ["syllabus", "curriculum", "module", "unit", "outline"])
        
        if not is_syllabus_query:
            # With DB storage, we don't have "--- Source: ---" headers exactly the same way
            # unless we reconstruct them. 
            # For now, we trust the raw text in the DB.
            pass 
        # -------------------------

        # IMPROVED RETRIEVAL: CONTEXT STUFFING
        # Gemini 2.0 Flash has a massive context window (1M tokens).
        # We should prioritize sending the FULL filtered text instead of naive keyword chunks.
        # 1 token ~= 4 chars. 1M tokens ~= 4M chars. 
        # We set a safe limit of 500,000 chars to be conservative and fast.
        
        if len(full_text) < 500000:
            print(f"DEBUG: Using Full Context (Length: {len(full_text)} chars)")
            context = full_text
        else:
            print(f"DEBUG: Text too large ({len(full_text)} chars), falling back to chunking.")
            # Filter context to avoid Rate Limit (TPM) issues with large files
            # Increased chunk_size to 2000 because PDF text is highly vertical/spaced
            context = self._retrieve_relevant_chunks(query, full_text, chunk_size=2000, overlap=200, top_k=3)
        
        # Clean context to remove annoying pdf newlines and excessive whitespace
        if context:
            # Replace newlines and multiple spaces with a single space
            import re
            context = re.sub(r'\s+', ' ', context).strip()

        # 2. Construct Prompt with Context
        prompt = f"""
You are an expert at decoding messy/broken text from PDFs.
The following context contains valid information but has "newlines" between words or broken sentences.

YOUR TASK:
1. Ignore the bad formatting. Treat the text as a continuous stream.
2. Find the answer to the User's Question in the text.
3. Summarize the answer clearly.

Context:
{context}

Question:
{query}

Answer:
"""
        try:
            # First attempt: Answer from Context
            if not self.model:
                    raise Exception("Google Generative AI Model not initialized.")
                    
            try:
                # Attempt 1: Try with currently selected context (Full or Chunked)
                response = self.model.generate_content(prompt)
                answer = response.text.strip()
            except Exception as api_err:
                    # FAILOVER STRATEGY: Try other models if the primary one fails (Quota/429/500)
                    print(f"DEBUG: Primary model failed ({api_err}). Attempting failover...")
                    
                    fallback_models = ["gemini-1.5-flash", "gemini-1.5-pro"]
                    success = False
                    
                    for model_name in fallback_models:
                        try:
                            print(f"DEBUG: Trying fallback model '{model_name}'...")
                            fallback_model = genai.GenerativeModel(model_name)
                            response = fallback_model.generate_content(prompt)
                            answer = response.text.strip()
                            success = True
                            print(f"DEBUG: Fallback to {model_name} SUCCESS.")
                            break
                        except Exception as fallback_err:
                            print(f"DEBUG: Fallback to {model_name} failed: {fallback_err}")
                            continue
                    
                    if not success:
                        # If all models fail, check specifically for Quota/Size issues to try Chunking
                        if ("429" in str(api_err) or "quota" in str(api_err).lower()) and len(context) > 0:
                            # RETRY STRATEGY:
                            # If we failed with massive context, try falling back to small chunks.
                            print("DEBUG: Full context failed (Quota). Retrying with Chunks...")
                            small_context = self._retrieve_relevant_chunks(query, full_text, top_k=3, chunk_size=2000, overlap=200) # Reduced chunks
                            
                            retry_prompt = f"""
You are an AI assistant.
Answer the question using the provided snippets.

Context:
{small_context}

Question:
{query}
"""
                            try:
                                # Try fallback models for retry prompt too
                                retry_success = False
                                for model_name in ["gemini-2.0-flash"] + fallback_models:
                                    try:
                                        fallback_model = genai.GenerativeModel(model_name)
                                        response = fallback_model.generate_content(retry_prompt)
                                        return response.text.strip()
                                    except:
                                        continue
                                        
                                if not retry_success:
                                    raise api_err # Propagate original error if everything fails

                            except Exception as retry_err:
                                    # If chunks fail, RAISE error so outer block handles it with "Force Show Data".
                                    raise retry_err
                        else:
                            # For other API errors, fail gracefully
                            raise api_err
            
            # Simple refusal check
            if "I cannot answer" in answer and len(answer) < 50:
                 pass # Logic preserved for logging if needed but log calls removed for cleanliness

            return answer

        except Exception as e:
            # Fallback: Web Search -> DISABLED PER USER REQUEST
            print(f"Ai Engine Error: {e}")
            
            # LAST RESORT: FORCE RETURN CONTEXT
            if context:
                clean_excerpt = str(context)[:3500] if context else ""
                if len(clean_excerpt) > 50:
                        return f"I found the relevant information in your notes, but I cannot summarize it right now (Error: {e}). Here is the exact text:\n\n\"{clean_excerpt}...\""
            
            return "I couldn't find the answer in your documents."

    def _retrieve_relevant_chunks(self, query, text, chunk_size=2000, overlap=200, top_k=3):
        """
        Simple keyword-based retrieval to select relevant chunks from text.
        Updated: Avoids cutting words in half by snapping to nearest space.
        """
        if not text:
            return ""

        # Basic stop words to ignore
        STOP_WORDS = {
            "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
            "in", "on", "at", "to", "for", "with", "by", "from", "of", "about",
            "what", "where", "when", "who", "why", "how", "this", "that", "these", "those",
            "current", "following", "given", "using", "use", "make", "example", "problem", 
            "solution", "chapter", "section", "value", "calculate", "find", "determine",
            "price", "cost", "ratio", "measure"
        }

        # Normalize query words and remove stop words
        query_words = set(query.lower().split())
        significant_words = {w for w in query_words if w not in STOP_WORDS}
        
        if not significant_words:
            # If query is only stop words (unlikely), fall back to original or return nothing
            return ""

        # Create chunks (Smart Slicing)
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # Adjust end to nearest space to avoid cutting words
            if end < text_len:
                # Look for last space within the last 50 chars of the chunk
                last_space = text.rfind(' ', start, end)
                if last_space != -1:
                    end = last_space
            
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Move start pointer, respecting overlap
            start = end - overlap
            if start < 0: start = 0 # Safety
            
            # Prevent infinite loop if chunk size is effectively 0
            if end == start:
                 start += 1
        scored_chunks = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            score = 0
            for word in significant_words:
                if word in chunk_lower:
                    score += 1
            scored_chunks.append((score, chunk))
        
        # Sort by score (descending)
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        # Select top chunks ONLY if they have a non-zero score
        top_chunks = [chunk for score, chunk in scored_chunks[:top_k] if score > 0]
        
        if not top_chunks:
            # If no significant keywords found, return empty to trigger Search
            return "" 
            
        return "\n...\n".join(top_chunks)

# Global instance
ai_engine = AIEngine()

import os
import google.generativeai as genai

# Try importing RAG dependencies, handle failure gracefully
RAG_AVAILABLE = False
try:
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.chains import RetrievalQA
    from langchain.schema import Document as LangChainDocument
    from langchain_community.utilities import GoogleSerperAPIWrapper
    RAG_AVAILABLE = True
except ImportError as e:
    print(f"Warning: RAG dependencies not found ({e}). AI features will be limited.")

class AIEngine:
    def __init__(self):
        # Initialize Google Gemini
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY not set")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            # Switch to 'gemini-2.0-flash-lite-preview' (Lite model)
            # 'gemini-2.0-flash' and '2.5-flash' hit strict 20 req/day limits.
            # Lite models typically offer higher thoroughput/quotas.
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite-preview')
        
        self.persist_directory = "db"
        
        # RAG Components (Only if available)
        self.embeddings = None
        self.vectordb = None
        self.llm = None
        self.search_tool = None

        if RAG_AVAILABLE:
            # Initialize Embeddings
            google_api_key = os.environ.get("GOOGLE_API_KEY")
            if google_api_key:
                self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
            
            # Initialize Vector Store
            self.vectordb = Chroma(
                persist_directory=self.persist_directory, 
                embedding_function=self.embeddings
            )
            
            self.llm = ChatGoogleGenerativeAI(model="gemini-pro", convert_system_message_to_human=True)
            self.search_tool = GoogleSerperAPIWrapper()

    def add_document(self, text, metadata):
        """Adds a document to the vector store (or file backup)."""
        if not RAG_AVAILABLE:
            try:
                # Append to a simple text file for "context stuffing"
                with open("knowledge_base.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n--- Source: {metadata.get('source', 'Unknown')} ---\n")
                    f.write(text)
                    f.write("\n")
                print(f"Document added to knowledge_base.txt: {metadata.get('source')}")
            except Exception as e:
                print(f"Error saving to knowledge base: {e}")
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_text(text)
        
        docs = [LangChainDocument(page_content=t, metadata=metadata) for t in texts]
        self.vectordb.add_documents(docs)
        self.vectordb.persist()

    def get_answer(self, query):
        """
        Retrieves answer from Knowledge Base or Search.
        """
        context = "" # Initialize context outside
        if not RAG_AVAILABLE:
            # 1. Retrieve Local Context
            full_text = ""
            if os.path.exists("knowledge_base.txt"):
                with open("knowledge_base.txt", "r", encoding="utf-8") as f:
                    full_text = f.read()

            # Filter context to avoid Rate Limit (TPM) issues with large files
            context = self._retrieve_relevant_chunks(query, full_text)
            
            # 2. Construct Prompt with Context
            prompt = f"""
You are a helpful and friendly AI assistant.
Your goal is to explain things in the MOST SIMPLE and EASY-TO-UNDERSTAND way possible.
Use the provided context from the user's uploaded documents.
If possible, use analogies or simple examples.
If the answer is NOT in the context, say exactly "SEARCH_REQUIRED".

Context:
{context}

Question: {query}
"""
            try:
                # First attempt: Answer from Context
                if not self.model:
                     raise Exception("Google Generative AI Model not initialized.")
                     
                try:
                    response = self.model.generate_content(prompt)
                    answer = response.text.strip()
                except Exception as api_err:
                     if "429" in str(api_err) or "quota" in str(api_err).lower():
                          # Fallback for API Quota Exceeded on Context
                          # If we found relevant context but can't summarize, return the snippets.
                          if context and len(context) > 50:
                               return f"I found the answer in your documents, but my AI quota is exhausted so I cannot summarize it. Here is the relevant text:\n\n{context[:2000]}..."
                          else:
                               raise Exception(f"Quota exceeded and no good context found: {api_err}")
                     else:
                          raise api_err

                if "SEARCH_REQUIRED" in answer or "I cannot answer" in answer:
                    raise Exception("Context insufficient")
                
                return answer

            except Exception as e:
                # Fallback: Web Search
                print(f"Searching web (Reason: {e})...")
                serper_key = os.environ.get("SERPER_API_KEY")
                if not serper_key:
                    return f"I couldn't find an answer in my database and Web Search is unavailable (missing API key). Reason: {e}"
                
                try:
                    # Manual Serper Call (since langchain wrapper is missing)
                    import requests
                    import json
                    
                    url = "https://google.serper.dev/search"
                    payload = json.dumps({"q": query})
                    headers = {
                        'X-API-KEY': serper_key,
                        'Content-Type': 'application/json'
                    }
                    
                    resp = requests.post(url, headers=headers, data=payload)
                    if resp.status_code != 200:
                         raise Exception(f"Serper API Error: {resp.status_code} - {resp.text}")
                         
                    search_data = resp.json()
                    
                    # Extract snippets
                    snippets = ""
                    if 'organic' in search_data:
                        for result in search_data['organic'][:5]:
                            snippets += f"- {result.get('title')}: {result.get('snippet')}\n"
                    
                    # Second Attempt: Answer from Search
                    search_prompt = f"""
You are a helpful AI assistant.
Answer the question using the following web search results.
Explain the answer in the MOST SIMPLE and EASY-TO-UNDERSTAND way possible.
Fill in any missing details to provide a complete answer.

Search Results:
{snippets}

Question: {query}
"""
                    if not self.model:
                        return f"[Web Search Result] {snippets}"

                    try:
                        search_response = self.model.generate_content(search_prompt)
                        return f"[Web Search] {search_response.text}"
                    except Exception as api_err:
                         if "429" in str(api_err) or "quota" in str(api_err).lower():
                              return f"[Web Search Result] (AI Summary Unavailable Due to Quota)\n{snippets}"
                         raise api_err
                         
                except Exception as se:
                     return f"I couldn't find an answer in my database and searching the web failed: {se}"

                except Exception as se:
                     return f"I couldn't find an answer in my database and searching the web failed: {se}"

        # If RAG IS Available (legacy/optional path)
        return "RAG functionality is currently disabled in this environment."

    def _retrieve_relevant_chunks(self, query, text, chunk_size=3000, overlap=500, top_k=5):
        """
        Simple keyword-based retrieval to select relevant chunks from text.
        This avoids sending the entire file which hits Token limits.
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

        # Create chunks
        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i:i + chunk_size]
            chunks.append(chunk)

        # Score chunks based on significant words only
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

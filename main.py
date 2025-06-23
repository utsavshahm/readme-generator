import re
import os
import tempfile
import git
import shutil
import stat
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_cohere import CohereEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import os
from langchain_google_vertexai import ChatVertexAI
from flask import jsonify
from langchain.chains import RetrievalQA
           
vectorstore = None

def handle_remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE) 
    func(path) 
    
def extract_useful_files(repo_path: str):
    included_extensions = ['.py', '.js', '.ts', '.json', '.md', '.txt', '.png', '.jpg', '.jpeg']
    excluded_dirs = {'node_modules', '__pycache__', '.git', 'venv', '.venv', 'env'}

    file_contents = []

    for root, dirs, files in os.walk(repo_path):
        # Skip excluded directories
        dirs = [d for d in dirs if d not in excluded_dirs]

        for file in files:
            if any(file.endswith(ext) for ext in included_extensions):
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    relative_path = os.path.relpath(file_path, repo_path)
                    file_contents.append({
                        "type" : "file",
                        'path': relative_path,
                        'content': content
                    })

                except Exception as e:
                    print(f"Skipping {file_path} due to read error: {e}")
                    # check if it is image, we can have it
                    if(file.endswith(ext) for ext in included_extensions): 
                        file_contents.append({
                            'type' : "image", 
                            'path' : os.path.relpath(file_path, repo_path)
                        })

    return file_contents

def validateURL(github_url : str):
    if not github_url:
        return {
            'status': 'error',
            'message': 'GitHub URL is required.'
        }, 400

    github_url_regex = r"^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(?:\.git)?\/?$"
    if not re.match(github_url_regex, github_url):
        return {
            'status': 'error',
            'message': 'GitHub URL is invalid.'
        }, 400
    
    return {
        'status' : 'ok', 
        'message' : "Valid Github url"
    }, 200

def cloneRepo(github_url : str): 

    temp_dir = tempfile.mkdtemp(prefix='repo_') # tempfile is used for creating temp files and directories
    print(f"Cloning repo into: {temp_dir}")
    repo = git.Repo.clone_from(github_url, temp_dir)

    return repo, temp_dir

def convert_files_to_documents(files):
    documents = []

    for file in files:
        if file['type'] != 'file':
            continue  # skip binary

        doc = Document(
            page_content=file['content'],
            metadata={'source': file['path']}
        )
        documents.append(doc)

    return documents

def chunk_documents(documents, chunk_size=1000, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(documents)
    return chunks

def create_vectorstore(chunks, persist_directory='chroma_store'):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    vector_store.persist()
    return vector_store

def processRepo(github_url: str):
    global vectorstore
    github_url = github_url.strip()

    msg, status_code = validateURL(github_url)
    if status_code != 200:
        return msg, status_code
    
    try:
        repo, temp_dir = cloneRepo(github_url)
        files = extract_useful_files(temp_dir)
        docs = convert_files_to_documents(files)
        chunks = chunk_documents(docs)
        vectorstore = create_vectorstore(chunks)

        print("====== Files present : =======\n")
        for file in files: 
            print(f"Path : {file['path']}, Type : {file['type']}", end="\n")

        print(f"====== Documents Generated : =======\n {len(docs)} total documents generated")

        print(f"====== Chunks Generated : =======\n {len(chunks)} total chunks generated")
        
        

    except git.exc.GitCommandError as e:
        error_msg = e.stderr.strip() if e.stderr else str(e)
        short_msg = error_msg.split('\n')[-3].split(':')[1] 
        return {'status': 'error', 'message': short_msg}, 400

    except Exception as e:
        # Catch any other non-git-related exception
        return {'status': 'error', 'message': str(e)}, 500
    # finally:
    #      # Clean up cloned repo
    #     try:
    #         repo.close()
    #         shutil.rmtree(temp_dir, onerror=handle_remove_readonly)
    #         print(f"Cleaned the directory!")
    #     except Exception as e:
    #         print(f"⚠️ Failed to clean up temp dir: {e}")


    return {
        'status': 'success',
        'message': 'GitHub repo cloned successfully and extracted files. ',
        'data': {
            'github_url': github_url,
            'local_path': temp_dir, 
            'vectorstore' : vectorstore
        }
    }, 200

def askQuery(query : str):
    global vectorstore
    
    if not query:
        return {
            'status': 'error',
            'message': 'Question is required.'
        }, 400

    try:
        # Create retriever from vectorstore
        llm = ChatVertexAI(model="gemini-pro")
        retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
        
        # Build RetrievalQA chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=True
        )

        # Run the query
        result = qa_chain({"query": query})
        answer = result["result"]
        sources = [doc.metadata.get("source") for doc in result["source_documents"]]

        return {
            'status': 'success',
            'answer': answer,
            'sources': list(set(sources))
        }, 200

    except Exception as e:
        return {
            'status': 'error',
            'message': f"Failed to answer question: {str(e)}"
        }, 500
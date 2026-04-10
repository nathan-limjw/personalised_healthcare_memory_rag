# Make sure Ollama is running
```bash

ollama serve
```

# Start the app
```bash

streamlit run app.py
```

# Building the Index
Click "📚 Build RAG Index" if not built yet
Wait for "Indexed 1182 chunks!" ✅

# Removing Cached Information and Memories
```bash

rm -rf ./data/rag_index \
       ./data/memory_stores\
       ./data/evaluation_results
```

# Running Test Cases

```bash 
cd  # ensure you are on the root directory
source venv/bin/activate
python3 -m eval.convert_test_cases_to_excel # can change Line 10 to change to more_test_cases
python3 -m eval.evaluate 

```

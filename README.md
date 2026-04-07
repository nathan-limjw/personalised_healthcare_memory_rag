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
python3 -m eval.evaluate 

```

nomic-embed-text:latest                           0a109f422b47    274 MB    28 minutes ago
gemma-local:latest                                ab83067c08d5    12 GB     4 weeks ago
gemma-3-4b-it-Q4_K_M:latest                       66b0d84bda94    2.5 GB    2 months ago
gte-small-Q4_K_M:latest                           3943390819af    29 MB     2 months ago
qwen3-4b-it-Q4_K_M:latest                         66b0d84bda94    2.5 GB    2 months ago
qwen3-4b-q4_k_m:latest                            66b0d84bda94    2.5 GB    2 months ago
deepseek-r1-32b:Q4_K_M                            d7cd415f1c39    19 GB     5 months ago
hf.co/unsloth/medgemma-27b-text-it-GGUF:Q3_K_S    f8070e054ba4    12 GB     8 months ago
hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_S    425c0e3e2bb5    15 GB     9 months ago
hf.co/unsloth/medgemma-27b-text-it-GGUF:Q4_K_M    3ea9af5c1cc9    16 GB     9 months ago
hf.co/unsloth/medgemma-4b-it-GGUF:Q8_0            4b4b4ac02543    5.0 GB    9 months ago
qwen3:8b                                          500a1f067a9f    5.2 GB    9 months ago
llama3:latest                                     365c0bd3c000    4.7 GB    9 months ago
qwen3:14b                                         7d7da67570e2    9.3 GB    11 months ago
gemma3:12b-it-qat                                 5d4fa005e7bb    8.9 GB    11 months ago
deepseek-r1:14b                                   ea35dfe18182    9.0 GB    12 months ago
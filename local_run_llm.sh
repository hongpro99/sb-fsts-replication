export ENV=local
uvicorn llm.server.api:app --host 0.0.0.0 --port 7003 --reload
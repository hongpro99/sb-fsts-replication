export ENV=local
uvicorn app.main:app --host 0.0.0.0 --port 7001 --reload
streamlit run dashboard_web/main.py
python llm/mcp_server.py --port 7005
uvicorn llm.api_server:app --host 0.0.0.0 --port 7003
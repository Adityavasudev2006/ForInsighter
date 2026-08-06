# Setup
1. cd backend
2. python -m venv venv && source venv/bin/activate
3. pip install -r requirements.txt
4. cp .env.example .env  -> fill in your keys
5. docker-compose up -d  -> starts Redis
6. python -m alembic init alembic (if using migrations) OR just run: python -c "from models.database import create_all; import asyncio; asyncio.run(create_all())"
7. Start backend: uvicorn main:app --reload --port 8000
8. Start Celery worker: celery -A tasks.celery_tasks worker --loglevel=info
9. Start frontend: cd .. && npm run dev

For Ollama local mode:
- Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh
- Pull model: ollama pull llama3.2
- Ollama runs automatically on port 11434

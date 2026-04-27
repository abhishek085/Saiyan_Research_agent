# Check containers are running
docker-compose ps

# Test SearxNG is alive
curl "http://localhost:8080/search?q=test&format=json" | python -m json.tool | head -20

# Test LM Studio is reachable from agent container
docker exec son-goku-agent curl -s http://host.docker.internal:1234/v1/models | python -m json.tool

# Check agent syntax without starting the bot
docker exec son-goku-agent python -m py_compile agent.py && echo "✅ syntax OK"

# Restart only agent (after code change)
docker-compose restart agent

# Rebuild after code changes
docker-compose up -d --build agent

# Shell into agent container
docker exec -it son-goku-agent bash

# Stop everything
docker-compose down

# Nuclear reset (removes volumes too)
docker-compose down -v
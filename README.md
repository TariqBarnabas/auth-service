Setup Steps:
1. Copy the .env.example data to .env
In terminal run this command:
2. docker compose up -d --build --scale api=2
3. alembic upgrade head
4. Connect to: http://localhost or http://localhost/docs


Architecture Choices:
FastAPI over PostgREST: 
Under the time constraint, PostgREST would have been the obvious choice.
However, I choice FastAPI over it for two distinct reasons
1. The scope of the project went out of postgREST's specialty, basic CRUD operations. It required
   more such as hashing, JWT, rate limiting and more. It did not make sense to use it under these circumstances
2. This is more a personal preference, having both SQLAlchemy and postgREST generate from my schema didnt feel right.

Traefik over NGINX:
Traefik was made to work with docker. Its built in automation meant I only had to set it up once and it would scale automatically per container.
However, if given more time I would have chosen NGINX because it handles heavier loads easier, and consumes less resources such as ram and cpu.

Argon2ID over bcrypt:
Argon2 was chosen for its built in features over bcrypt. One draw back is that it is memory hard, meaning to scale it would cause a drawback.
However, for a minimal auth service i believe it is fine. In my opinion, this is my most flaky choice.

SQLAlchemy + Alembic:
When I heard about SQLAlchemy's built in pooler

Docker Swarm over K8:
Chosen for simplicity and time. Swarm integrates directly with docker compose, making it the simpler of the two option to set up and use.

Scalability:
To my knowledge, Postgres handles large tables well. The issue would arise when searching a table with 10 million users. 
In order to fix this, I made email unique index.
The API's work as the load balancers, which could scale becasue they do not hold a server-local state. 
Traefik is automatic, means it doesnt need a seperate configuration per load balancer.
Redis handles the latency state and possible high frequences the app needs, giving it elastcitiy.
Connection pooling is handled by SQLAlchemy's async engine. For futerproofing, a pgbouncer would be the natural next step.

# AdamHUB - Installation VPS

Ce document couvre le cas vise:

- AdamHUB tourne dans des conteneurs Docker sur ton VPS
- tu veux une procedure d'installation et de mise a jour simple
- un client assistant compatible peut etre branche plus tard, mais n'est pas requis pour faire tourner AdamHUB

## 1. Prerequis VPS

- Docker
- Docker Compose plugin
- Git
- un reverse proxy TLS si tu exposes AdamHUB publiquement

## 2. Installation AdamHUB sur le VPS

Clone le repo:

```bash
git clone https://github.com/adamelhirch/adamHub.git
cd adamHub
```

Prepare l'environnement VPS:

```bash
cp .env.vps.example .env
```

Remplis au minimum:

```env
ADAMHUB_API_KEYS=un_secret_long_et_random
ADAMHUB_API_KEY=un_secret_long_et_random
ADAMHUB_PUBLIC_BASE_URL=https://adamhub.ton-domaine.com
ADAMHUB_ALLOW_ORIGINS=https://adamhub.ton-domaine.com
VITE_API_URL=https://adamhub.ton-domaine.com/api/v1
VITE_API_KEY=un_secret_long_et_random

POSTGRES_DB=adamhub
POSTGRES_USER=adamhub
POSTGRES_PASSWORD=un_autre_secret_db

ADAMHUB_PORT=8000
```

Important:

- le backend AdamHUB valide les requetes avec `ADAMHUB_API_KEYS`
- `ADAMHUB_API_KEY` est juste un miroir de confort pour la doc et certains outils
- `VITE_API_URL` et `VITE_API_KEY` sont injectees au build du frontend
- apres toute modification de `VITE_*`, il faut rebuild l'image avec `docker compose ... up -d --build`
- le client assistant n'a pas besoin de tourner dans le meme `docker compose`

Lance l'installation:

```bash
./scripts/install-vps.sh
```

Ce script:

- build l'image AdamHUB
- lance Postgres
- lance l'API AdamHUB
- applique automatiquement les migrations Alembic au demarrage du conteneur

## 3. Ce que lance vraiment le conteneur

Le flux de demarrage est:

1. le conteneur attend que la DB soit joignable
2. `alembic upgrade heads`
3. `uvicorn app.main:app`

Donc pour une mise a jour, tu n'as pas besoin de lancer les migrations a la main.

## 4. URLs utiles

- Health: `https://adamhub.ton-domaine.com/health`
- Swagger: `https://adamhub.ton-domaine.com/docs`
- Skill manifest: `https://adamhub.ton-domaine.com/api/v1/skill/manifest`
- Skill execute: `https://adamhub.ton-domaine.com/api/v1/skill/execute`

## 5. Le pack assistant est optionnel

AdamHUB tourne tres bien sans client assistant.

Si tu veux brancher un client compatible plus tard, le skill maitre a donner est:

- `adamhub-assistant/SKILL.md`

Mais il faut fournir le dossier `adamhub-assistant/` en entier, pas seulement le fichier principal, car il depend de:

- `adamhub-assistant/references/*`
- `adamhub-assistant/*/SKILL.md`

En pratique:

- soit tu copies le dossier `adamhub-assistant/` dans le repertoire de skills de ton runtime assistant
- soit tu le montes comme volume dans le conteneur du runtime assistant

## 6. Variables d'environnement a donner au runtime assistant

Minimum:

```env
ADAMHUB_API_URL=https://adamhub.ton-domaine.com
ADAMHUB_URL=https://adamhub.ton-domaine.com
ADAMHUB_API_KEY=un_secret_long_et_random
```

Si le runtime assistant tourne dans le meme reseau Docker que AdamHUB, tu peux utiliser l'URL interne:

```env
ADAMHUB_API_URL=http://adamhub-api:8000
ADAMHUB_URL=http://adamhub-api:8000
ADAMHUB_API_KEY=un_secret_long_et_random
```

Le plus simple est:

- dans `.env` de ton backend VPS: `ADAMHUB_API_KEYS=un_secret_long_et_random`
- dans l'environnement du runtime assistant: `ADAMHUB_API_KEY=un_secret_long_et_random`
- mirror l'URL dans `ADAMHUB_API_URL` et `ADAMHUB_URL` si ton runtime assistant n'est pas strict sur le nom exact

Un exemple pret a copier est fourni dans `adamhub-assistant/.env.example`.

## 7. Exemple de montage Docker pour le runtime assistant

Exemple de principe seulement, a adapter au chemin de skills attendu par ton runtime:

```yaml
services:
  assistant:
    image: ton-image-assistant
    environment:
      ADAMHUB_API_URL: https://adamhub.ton-domaine.com
      ADAMHUB_API_KEY: un_secret_long_et_random
    volumes:
      - ./adamhub-assistant:/app/skills/adamhub-assistant:ro
```

Le point important est:

- `adamhub-assistant/SKILL.md` = skill maitre
- le dossier `adamhub-assistant/` complet doit rester disponible

## 8. Verification du runtime assistant

Le runtime assistant doit pouvoir appeler:

```bash
curl -H "X-API-Key: un_secret_long_et_random" \
  https://adamhub.ton-domaine.com/api/v1/skill/manifest
```

Puis:

```bash
curl -H "X-API-Key: un_secret_long_et_random" \
  -H "Content-Type: application/json" \
  -d '{"action":"task.create","input":{"title":"test depuis assistant","priority":"medium"}}' \
  https://adamhub.ton-domaine.com/api/v1/skill/execute
```

## 9. Mettre a jour AdamHUB apres installation

Sur le VPS:

```bash
cd /chemin/vers/adamHub
./scripts/update-vps.sh
```

Ce script fait:

1. `git pull --ff-only`
2. rebuild du conteneur
3. restart du service
4. migration auto au demarrage

Si tu veux juste redemarrer sans pull:

```bash
docker compose -f docker-compose.vps.yml up -d
```

## 10. Si tu veux une URL publique stable

Mets un reverse proxy devant le port `8000` et configure:

- `ADAMHUB_PUBLIC_BASE_URL=https://adamhub.ton-domaine.com`
- `ADAMHUB_ALLOW_ORIGINS=...`

Le runtime assistant peut ensuite pointer vers:

- l'URL publique si le runtime assistant est externe
- l'URL Docker interne si le runtime assistant est sur le meme hote/reseau

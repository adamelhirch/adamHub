# AdamHUB - Installation VPS

Ce document couvre le cas vise:

- AdamHUB tourne dans des conteneurs Docker sur ton VPS
- tu veux une procedure d'installation et de mise a jour simple
- OpenClaw peut etre branche plus tard, mais n'est pas requis pour faire tourner AdamHUB

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
ADAMHUB_PUBLIC_BASE_URL=https://adamhub.ton-domaine.com
ADAMHUB_ALLOW_ORIGINS=https://adamhub.ton-domaine.com

POSTGRES_DB=adamhub
POSTGRES_USER=adamhub
POSTGRES_PASSWORD=un_autre_secret_db

ADAMHUB_PORT=8000
```

Important:

- le backend AdamHUB valide les requetes avec `ADAMHUB_API_KEYS`
- `ADAMHUB_API_KEY` est juste un miroir de confort pour la doc et certains outils
- OpenClaw n'a pas besoin de tourner dans le meme `docker compose`

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
2. `alembic upgrade head`
3. `uvicorn app.main:app`

Donc pour une mise a jour, tu n'as pas besoin de lancer les migrations a la main.

## 4. URLs utiles

- Health: `https://adamhub.ton-domaine.com/health`
- Swagger: `https://adamhub.ton-domaine.com/docs`
- Skill manifest: `https://adamhub.ton-domaine.com/api/v1/skill/manifest`
- Skill execute: `https://adamhub.ton-domaine.com/api/v1/skill/execute`

## 5. OpenClaw est optionnel

AdamHUB tourne tres bien sans OpenClaw.

Si tu veux brancher OpenClaw plus tard, le skill maitre a donner est:

- `openclaw/SKILL.md`

Mais il faut fournir le dossier `openclaw/` en entier, pas seulement le fichier principal, car il depend de:

- `openclaw/references/*`
- `openclaw/skills/*`

En pratique:

- soit tu copies le dossier `openclaw/` dans le repertoire de skills de ton instance OpenClaw
- soit tu le montes comme volume dans le conteneur OpenClaw

## 6. Variables d'environnement a donner a OpenClaw

Minimum:

```env
ADAMHUB_API_URL=https://adamhub.ton-domaine.com
ADAMHUB_API_KEY=un_secret_long_et_random
```

Si OpenClaw tourne dans le meme reseau Docker que AdamHUB, tu peux utiliser l'URL interne:

```env
ADAMHUB_API_URL=http://adamhub-api:8000
ADAMHUB_API_KEY=un_secret_long_et_random
```

Le plus simple est:

- dans `.env` de ton backend VPS: `ADAMHUB_API_KEYS=un_secret_long_et_random`
- dans l'environnement d'OpenClaw: `ADAMHUB_API_KEY=un_secret_long_et_random`

Un exemple pret a copier est fourni dans `openclaw/.env.example`.

## 7. Exemple de montage Docker pour OpenClaw

Exemple de principe seulement, a adapter au chemin de skills attendu par ton image OpenClaw:

```yaml
services:
  openclaw:
    image: ton-image-openclaw
    environment:
      ADAMHUB_API_URL: https://adamhub.ton-domaine.com
      ADAMHUB_API_KEY: un_secret_long_et_random
    volumes:
      - ./openclaw:/app/skills/adamhub:ro
```

Le point important est:

- `openclaw/SKILL.md` = skill maitre
- le dossier `openclaw/` complet doit rester disponible

## 8. Verification OpenClaw

OpenClaw doit pouvoir appeler:

```bash
curl -H "X-API-Key: un_secret_long_et_random" \
  https://adamhub.ton-domaine.com/api/v1/skill/manifest
```

Puis:

```bash
curl -H "X-API-Key: un_secret_long_et_random" \
  -H "Content-Type: application/json" \
  -d '{"action":"task.create","input":{"title":"test depuis openclaw","priority":"medium"}}' \
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

OpenClaw peut ensuite pointer vers:

- l'URL publique si OpenClaw est externe
- l'URL Docker interne si OpenClaw est sur le meme hote/reseau

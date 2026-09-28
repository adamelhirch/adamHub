import asyncio
from app.services.notifications import send_push_notification
from app.core.config import get_settings

async def main():
    settings = get_settings()
    topic = settings.ntfy_topic
    
    if not topic:
        print("❌ ERREUR : La variable ADAMHUB_NTFY_TOPIC n'est pas définie dans ton fichier .env.")
        print("👉 Ajoute par exemple : ADAMHUB_NTFY_TOPIC=adamhub_secret_652_adamelhirch dans le fichier .env")
        return

    print(f"📡 Envoi d'une notification de test vers le canal : {topic}...")
    
    success = await send_push_notification(
        title="✅ Test AdamHUB",
        message="Si tu reçois ça, NTFY fonctionne parfaitement ! Tu es prêt à recevoir les alertes frigo et calendrier.",
        priority=4,  # Priorité haute
        tags=["rocket", "tada", "bell"] # Emojis
    )
    
    if success:
        print("✅ Succès ! Regarde ton iPhone ou ton Mac.")
        print(f"🔗 Tu peux aussi voir/télécharger l'application web ici : https://ntfy.sh/{topic}")
    else:
        print("❌ Échec de l'envoi. Vérifie ta connexion internet.")

if __name__ == "__main__":
    asyncio.run(main())

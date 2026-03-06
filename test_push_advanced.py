import asyncio
from app.services.notifications import send_push_notification
from app.core.config import get_settings

async def main():
    settings = get_settings()
    topic = settings.ntfy_topic
    
    if not topic:
        print("❌ ERREUR : La variable ADAMHUB_NTFY_TOPIC n'est pas définie dans ton fichier .env.")
        return

    print(f"📡 Envoi d'une notification NTFY AVANCÉE vers le canal : {topic}...")
    
    success = await send_push_notification(
        title="📱 Notification Interactive AdamHUB",
        message="Regarde bien : j'ai une icône personnalisée, et si tu cliques sur le bouton en dessous, je t'emmène sur ton Dashboard Web (simulé) !",
        priority=4,
        tags=["brain", "sparkles"],
        icon="https://cdn-icons-png.flaticon.com/512/3208/3208947.png", # Apple style icon
        click="https://www.apple.com/iphone-17/", # URL default click action
        actions=[
            {
                "action": "view",
                "label": "Ouvrir Dashboard 🌐",
                "url": "https://adamhub.local",
                "clear": True
            },
            {
                "action": "http",
                "label": "Fausse Action Backend ⚙️",
                "url": "https://ntfy.sh",
                "method": "POST",
                "clear": True
            }
        ]
    )
    
    if success:
        print("✅ Succès ! Regarde ton iPhone.")
        print("Teste de cliquer n'importe où sur la notification, ou sur les boutons d'action.")
    else:
        print("❌ Échec de l'envoi.")

if __name__ == "__main__":
    asyncio.run(main())

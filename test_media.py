import asyncio
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

async def main():
    try:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = manager.get_current_session()
        if session:
            info = await session.try_get_media_properties_async()
            print(f"Title: {info.title}")
            print(f"Artist: {info.artist}")
        else:
            print("No active session")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())

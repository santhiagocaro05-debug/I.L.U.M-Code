import asyncio
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

async def main():
    manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
    session = manager.get_current_session()
    if session:
        tl = session.get_timeline_properties()
        if tl:
            print(f"End time type: {type(tl.end_time)}")
            print(f"End time: {tl.end_time}")
            print(f"Position type: {type(tl.position)}")
            print(f"Position: {tl.position}")
        else:
            print("No timeline properties")
    else:
        print("No active session")

if __name__ == '__main__':
    asyncio.run(main())

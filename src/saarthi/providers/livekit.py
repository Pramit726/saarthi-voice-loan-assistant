from __future__ import annotations

from datetime import timedelta

from livekit import api


class LiveKitTokenProvider:
    def __init__(self, *, url: str, api_key: str, api_secret: str, ttl_seconds: int = 900) -> None:
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.ttl_seconds = ttl_seconds

    def issue(self, *, room: str, participant_identity: str, participant_name: str) -> str:
        return (
            api.AccessToken(self.api_key, self.api_secret)
            .with_identity(participant_identity)
            .with_name(participant_name)
            .with_ttl(timedelta(seconds=self.ttl_seconds))
            .with_grants(api.VideoGrants(room_join=True, room=room, can_publish=True, can_subscribe=True))
            .to_jwt()
        )

    async def dispatch_agent(self, *, room: str, agent_name: str) -> None:
        client = api.LiveKitAPI(self.url, self.api_key, self.api_secret)
        try:
            await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(agent_name=agent_name, room=room)
            )
        finally:
            await client.aclose()

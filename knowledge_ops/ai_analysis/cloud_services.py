from __future__ import annotations


class DisabledCloudClient:
    def analyze(self, *args, **kwargs):
        raise RuntimeError("Cloud AI calls are intentionally disabled in estimate mode.")


VisionClient = DisabledCloudClient
DocumentAIClient = DisabledCloudClient
VideoIntelligenceClient = DisabledCloudClient
SpeechToTextClient = DisabledCloudClient

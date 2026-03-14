from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_secrets_file("src/youtube/client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

# Save the credentials to token.json
with open("src/youtube/token.json", "w") as token_file:
    token_file.write(creds.to_json())

print("Token saved to src/youtube/token.json")

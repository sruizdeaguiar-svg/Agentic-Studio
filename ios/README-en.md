# Agentic Studio for iPhone and iPad

[Español](README-es.md) · English

Universal client for iOS/iPadOS 17 or later. The Mac runs models and tools. The device displays conversations, authorized projects, files, reviews, activity and generation settings without downloading weights.

Open `AgenticMobile.xcodeproj` in Xcode, select the AgenticMobile target and configure your own signing team. The public project has an empty team setting and no personal certificates or provisioning profiles. `../build-ios.sh` builds the simulator app and **unsigned** ARM64 IPA. Physical installation requires valid signing.

On the Mac, open **Conexiones → Red local**, select authorized projects and show the QR. On the device, tap **Escanear QR del Mac**. The code is single-use and expires after five minutes; the app validates the TLS fingerprint. You can also paste the pairing link. Camera and local-network permissions are requested when needed. Photos and microphone access are not required.

The Mac backend enforces tools and permissions. Mobile clients cannot administer OAuth, engines, folders or global permissions. Permission changes revoke pairing; stopping the gateway revokes all clients.

The web interface is served by the Mac. Automated tests cover three screen sizes, permissions, pairing, HTTPS and revocation. A build is not a physical-device test. Version 0.5.0 was installed on an authorized iPad; the user confirmed its new name and icon. Physical QR scanning and an actual response were verified on the previous version.

Do not share the iPad screen through Device Hub while using its camera: that connection can reserve multimedia resources. Consult Apple's Device Hub limitations if video turns black. Testing this app does not require opening Device Hub.

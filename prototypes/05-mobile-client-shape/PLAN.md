# Prototype 05 — Mobile client shape spike

**Status:** planned (not built).
**Validates:** issue [#5](https://github.com/sergiunagy/docparse/issues/5) — “Prototype:
mobile client shape (PWA vs Ionic vs native)”.

This document is an execution plan for a later hands-on session. No Android tooling,
emulator, phone configuration, deployment, scaffold, or prototype build has been performed as
part of writing it.

## 1. Design question

`docparse` needs a client from which a family member can trigger ingestion of an official
German PDF. The domain context says that the first Source is a file folder and that ingestion
must be triggerable from mobile ([`CONTEXT.md`](../../CONTEXT.md)); the client remains separate
from the gateway and ingestion services under
[ADR-0002](../../docs/adr/0002-service-oriented-from-day-one.md). Issue #5 asks for cheap,
runnable evidence rather than a framework comparison assembled from feature lists.

Build three disposable Android-facing tracer bullets and run the same journey on the same
Pixel 7 Pro, preferably on one local emulator first:

1. an **installable Angular PWA** in Android Chrome;
2. an **Ionic + Angular app**, packaged for Android with Capacitor; and
3. a **native Android baseline in Kotlin + Jetpack Compose**.

Kotlin/Compose is the fixed third arm for this spike so that “native feel” has a direct Android
baseline and the experiment stays to three implementations. Choosing it as the comparator is
**not** a recommendation to ship native Android. React Native, Flutter, Kotlin Multiplatform,
Ionic-on-the-web, and a Trusted Web Activity remain possible later alternatives, but adding them
now would weaken the controlled comparison and exceed a cheap spike.

The spike must answer with observed evidence:

- **Angular skill reuse:** what UI, state, TypeScript, tooling, and tests carry over from normal
  Angular work, and where does each arm force platform-specific knowledge or native code?
- **Phone-triggered ingestion:** can the user start the domain trigger from the launcher and
  hand a PDF to the installed client from Android Files/Drive-style UI, with an acceptable
  fallback when direct share is unavailable?
- **Distribution/app-store friction:** what is actually required to install and update a test
  build, and what additional release obligations are documented for the likely distribution
  route? Local sideloading is not evidence of Play review speed.
- **Feel:** on the Pixel, does launch, navigation, system file selection/share handoff, back,
  resume, offline relaunch, and status feedback feel coherent and responsive?

This plan deliberately makes no winning recommendation. Documentation establishes what to
try; only the later builds and human evaluation establish how the options behave here.

## 2. Comparable tracer-bullet scope

### 2.1 The shared phone-ingestion journey

Use one synthetic, non-sensitive, two-page PDF named `synthetic-finanzamt-notice.pdf`, copied
to the Android Downloads folder. Its bytes, filename, MIME type, expected byte count, and
SHA-256 must be identical for every arm and device.

Each arm implements exactly these paths:

1. **Launcher/source trigger (required domain path).** Launch app → tap **Check fixture source
   now** → create the canonical local command
   `{"sourceId":"fixture-folder","requestedBy":"mobile","buildId":"…"}` → show the same
   deterministic `Queued` receipt. This proves that the mobile client can originate the user
   action; it does not claim to prove the future gateway or folder connector.
2. **Android share handoff (required capability probe).** In Android Files, select the synthetic
   PDF → Share → choose the installed tracer bullet → land on the review screen with filename,
   MIME type, byte count, and the first 12 characters of its SHA-256 → tap **Queue this PDF** →
   show the same receipt shape.
3. **In-app picker fallback (required).** Launch app → tap **Choose PDF** → use the system file
   picker → select the same fixture → reach the same review and receipt screens.

For the PWA, path 2 is specifically a Web Share Target experiment and therefore must be tested
only after the PWA is genuinely installed. For Ionic and native, it is an Android
`ACTION_SEND`/content-URI experiment. A path that cannot be made to work inside its timebox is
a recorded result, not permission to substitute a different scenario silently. Path 3 remains
the common fallback.

The “queue” adapter is local and deterministic: validate/read the selected bytes, wait a fixed
750 ms, and derive a receipt ID from the fixture hash. **Do not upload or persist the PDF and do
not add a real backend.** Every arm displays the canonical request/receipt JSON behind a
collapsed **Evidence details** disclosure so semantic parity can be checked without making the
prototype UI into a debugging screen.

### 2.2 Shared screens and acceptance contract

All arms use the same copy, information architecture, assets, and state machine:

```text
Home
  ├─ Check fixture source now → Queuing → Receipt
  └─ Choose PDF → Review selected PDF → Queue this PDF → Queuing → Receipt
Android share target ─────────→ Review selected PDF
```

Required UI states are `idle`, `reading`, `ready`, `queuing`, `queued`, and `error`. Required
behaviour:

- launch from the home-screen/app-drawer icon into a standalone app surface;
- only advertise/accept one `application/pdf` file, reject the wrong MIME type and multiple
  files with the same message, and never request broad storage access;
- show filename, MIME, byte count, and truncated SHA-256 before queueing;
- preserve the review state through one background/foreground cycle where the platform allows
  the granted URI/file to remain readable; record loss of state rather than inventing broader
  permissions;
- Android system Back returns from receipt → review → home and never traps or unexpectedly exits;
- after one successful online/install load, airplane-mode relaunch opens the shell and completes
  the entirely local fixture journey;
- expose the implementation-neutral build ID and an **Export evidence** action that copies or
  downloads a small JSON event log containing timestamps and states, but no file contents or
  absolute user paths;
- no login, document understanding, translation, camera capture, notifications, or production
  styling.

Use the same neutral Material-like visual tokens: typography scale, colours, spacing, app icon,
button order, transitions (none beyond platform defaults), copy, and accessibility labels. Name
the installed apps `Docparse A`, `Docparse B`, and `Docparse C`; randomise the mapping from A/B/C
to technologies immediately before the scored physical-device session and reveal it only after
subjective scoring. This is imperfect blinding—the install mechanics can reveal a PWA—but it
reduces framework-brand priming.

### 2.3 Arm-specific implementation boundary

| Arm | Minimum mechanism to test | Allowed platform-specific work | Timebox after common UI works |
| --- | --- | --- | --- |
| Angular PWA | Current Angular standalone app, `@angular/pwa`, manifest/icons, production service worker, installed from Android Chrome; `share_target` accepts one PDF | Manifest and service-worker/share-target handler only | 4 hours for direct share |
| Ionic + Angular | Current compatible Ionic Angular standalone setup, Capacitor Android debug APK; Ionic UI where equivalent | Android manifest plus the smallest documented Capacitor/custom plugin bridge needed to receive one PDF content URI | 4 hours for direct share |
| Native Android | Kotlin, Jetpack Compose, Material 3 debug APK; Storage Access Framework picker | Manifest intent filter and idiomatic `ACTION_SEND`/content-URI handling | 4 hours for direct share |

Before scaffolding, the future agent must freeze current mutually compatible versions from
first-party documentation. Do not force all arms onto a stale Angular or Android version merely
to make the table look symmetrical. Record framework, CLI, Node, JDK, Gradle/AGP, compile SDK,
target SDK, Chrome/WebView, phone OS, and emulator image versions in the evidence log.

## 3. Controlled variables and fairness rules

Hold these constant:

- one developer machine, Node version where applicable, test operator, Pixel 7 Pro, emulator API
  image, fixture bytes, app copy/assets, screen/state contract, no backend, and test script;
- release-like optimized web assets for PWA/Ionic and ordinary debug APKs for both Android
  packages; do not compare an Angular dev server with a packaged native release build;
- warm-up each arm once, then collect three measured trials in a randomised order; report all
  three and the median, not the best run;
- clear each arm’s app/site data before the first-install trial, but not between ordinary launch
  trials; document exactly when Chrome cache, service worker, or app data is cleared;
- use the system picker and the same Files app/provider; no arm gets a custom picker;
- accept only user-selected content URIs/files. No arm gets `MANAGE_EXTERNAL_STORAGE`, broad
  storage permission, background service, analytics SDK, cloud host, or special OEM setting;
- one agent implements all arms from the written acceptance contract. Record elapsed time and
  interventions rather than using line count alone as a productivity proxy;
- cap polish at contract parity. If one framework supplies attractive defaults, keep them and
  score that as evidence; do not spend extra hours making the other arms imitate it.

Record unavoidable differences explicitly: a PWA’s Chrome-managed installation/update path,
Ionic’s WebView/runtime, native Android’s platform widgets/lifecycle, and framework-generated
files. “Controlled” means equivalent user outcome, not pretending the platforms are identical.

### Instrumentation without benchmark theatre

For each arm capture:

- elapsed minutes for scaffold, first desktop/preview render, first successful build, first
  emulator run, first Pixel run, picker path, and direct-share path;
- human-authored/modified files and non-generated lines by category: shared Angular/domain UI,
  web/PWA, Ionic, Capacitor/native bridge, Kotlin/Compose, manifest/build configuration, tests;
- dependency count, compressed web build size or APK size, requested permissions, and warnings;
- three manual or screen-record-derived timings for cold icon tap → usable Home, Files Share tap
  → usable Review, Choose PDF tap → usable Review, and Queue tap → Receipt (the last should be
  approximately the controlled 750 ms plus UI overhead);
- tap count and user-visible prompts for clean install, first run, both ingestion paths, update,
  and uninstall;
- functional pass/fail plus logs for wrong type, multiple files, Back, background/resume,
  airplane-mode relaunch, rotation once, and update from build ID 1 to build ID 2;
- operator notes and Pixel screen recording. Treat these timings as comparative observations on
  one device, not general performance benchmarks.

## 4. Setup gates and stop rules

Do not move past a gate until its evidence is recorded.

### Gate 0 — research/version gate (agent-owned)

- Re-open every primary source in §11, note access date and current versions, and distinguish
  specification, framework claim, browser-specific support, and observed behaviour.
- Confirm the current PWA share-target requirements for a single PDF, the supported Ionic Angular
  matrix, the supported Capacitor/Android toolchain, and current Play requirements.
- Confirm whether Capacitor has a first-party receive-share API. If it does not, document that
  before choosing the minimal custom Android bridge; do not mistake the outbound Share plugin for
  inbound share support.
- Produce the A/B/C randomisation key but keep it out of the evaluator-facing UI.

### Gate 1 — environment readiness (USER ACTION REQUIRED)

The user completes §7 and reports: Android Studio opens, the chosen SDK/platform tools are
installed, the AVD boots, `adb devices` sees the AVD, and—if physical debugging is used—the Pixel
appears as an authorised device. The agent may diagnose reported output but must not install the
IDE/SDK, create the AVD, change phone settings, or accept licences for the user.

### Gate 2 — private transport/fixture gate (joint)

- Agent supplies fixture SHA-256 and build checksums; user confirms the same fixture is visible in
  emulator and Pixel Downloads.
- Agent serves the production PWA locally and proposes an exact `adb reverse` mapping so device
  `localhost` reaches the workstation. No public deployment or third-party tunnel is allowed.
- User confirms the page opens in Pixel Chrome before installing it. If local PWA installation or
  share-target registration cannot be exercised through this secure/local setup, stop and agree
  on a synthetic-data-only HTTPS host; do not improvise a public upload.

### Gate 3 — emulator functional parity (agent build + USER installation)

All three arms pass launcher trigger, picker fallback, and the common state contract on one AVD.
Attempt direct share inside each arm’s four-hour timebox. Record a failure and continue if the
platform path remains blocked. Do not start subjective scoring on the emulator.

### Gate 4 — Pixel functional parity (USER installation + joint run)

The user installs each checksummed artifact/PWA and runs the unscored familiarisation script.
Any crash, unreadable fixture, accidental permission request, missing launcher install, or stale
build ID returns that arm to the agent once. After one repair cycle, an unresolved issue is a
prototype result; do not endlessly polish one arm.

### Gate 5 — scored HITL session

Freeze builds and browser/OS versions, randomise trial order, execute §8, export evidence, reveal
A/B/C, and only then apply §9’s decision rules.

## 5. Future agent-owned research/build tasks

These are tasks for a later implementation session, not work completed by this plan.

### Phase A — source verification and experiment sheet

1. Read the first-party sources in §11 and create `NOTES.md` with dated/versioned facts,
   unresolved questions, and exact commands proposed. Secondary articles may help discover an
   API but cannot be the sole basis for a constraint or scoring claim.
2. Inventory the existing machine without changing it: OS/CPU/RAM, Node/npm, Java, Android Studio,
   SDK, `adb`, Chrome, hardware acceleration, available disk. Present missing prerequisites to
   the user as §7 actions; never install them silently.
3. Freeze arm versions and package IDs; write the common acceptance checklist and JSON event
   schema before framework code.
4. Create the deterministic synthetic PDF and publish its SHA-256. It must contain obviously fake
   names, IDs, amounts, and a large `SYNTHETIC — NOT AN OFFICIAL DOCUMENT` watermark.

### Phase B — cheapest vertical slice per arm

5. Build the Angular PWA first because it defines the maximum direct Angular reuse. Add a valid
   manifest/icons and Angular production service worker, implement picker + local receipt, then
   attempt installed Web Share Target PDF receipt. Test the production output, not `ng serve`.
6. Build Ionic Angular from the same acceptance contract without copying generated PWA machinery.
   Use Angular standalone APIs and Ionic components; package with Capacitor. Implement picker and
   local receipt, then use the smallest first-party-supported/custom Android bridge for inbound
   `ACTION_SEND` if needed. Record every Kotlin/Java/manifest change separately.
7. Build the Kotlin/Compose baseline with Material 3, Activity Result/Storage Access Framework,
   content-resolver hashing, and an `ACTION_SEND` PDF intent filter. Keep architecture flat and
   disposable—one activity, a small state holder, no DI/database/network layer.
8. Give each arm only small contract-level tests: state/receipt unit tests, wrong-type validation,
   and one launch/picker/share smoke test where the platform harness makes it cheap. Do not build
   production test architecture.

### Phase C — reproducibility and evidence capture

9. Produce production PWA assets and debug APKs with embedded build IDs; record checksums, build
   duration, sizes, dependency lockfiles, package/manifest permissions, and exact commands.
10. Provide a local static server command and target-specific `adb reverse` commands. Bind only to
    loopback where possible. Verify there is no analytics, remote font, CDN asset, or network call.
11. Run the emulator checklist first, collect logs/screenshots, and repair at most once per arm.
12. Hand the user artifact paths/checksums and the explicit install/update/uninstall script in §7.
    The agent does not configure the phone or silently deploy an APK.
13. Facilitate the Pixel session, timestamp observations, collect exported JSON, and assemble the
    matrix. Keep raw facts separate from interpretation.
14. Write the prototype `README.md` only when runnable, with clean-room reproduction steps. Write a
    concise findings summary only after HITL. Do not update ADRs or issue #5 until the evidence is
    reviewed and the user explicitly requests publication.

### Files expected at build time

```text
prototypes/05-mobile-client-shape/
├── PLAN.md                         # this file
├── NOTES.md                        # dated source/version and implementation log
├── README.md                       # added only after runnable builds exist
├── shared/
│   ├── acceptance.md               # canonical copy, states, JSON shape, test script
│   └── synthetic-finanzamt-notice.pdf
├── angular-pwa/                    # disposable Angular PWA
├── ionic-angular/                  # disposable Ionic Angular + Capacitor app
├── native-android/                 # disposable Kotlin/Compose app
└── out/                            # ignored raw logs, recordings, screenshots, score sheets
```

At build time add a prototype-local `.gitignore` for generated dependencies/build outputs,
keystores, local SDK paths, `out/`, and any copied device data. Commit lockfiles and the synthetic
fixture; never commit debug/release signing keys, real documents, exported user paths, or device
identifiers.

## 6. Agent handoff package before device work

The agent must give the user one short manifest before asking for any installation:

- A/B/C display name and private technology mapping;
- PWA local URL and expected manifest/build ID;
- APK absolute paths, package IDs, byte sizes, SHA-256 checksums, and minimum/target Android API;
- fixture path, size, and SHA-256;
- exact AVD and physical-device install/update/uninstall commands, each with the intended serial
  selected explicitly so an emulator build cannot land on the phone accidentally;
- permissions expected: ideally none at runtime because selection uses browser/system picker and
  URI grants; Internet may appear as a normal manifest permission in packaged web clients;
- any observed build warning or arm-specific limitation;
- rollback steps and how to disable/revoke debugging after the session.

No Play developer account, production signing key, public host, or real document is needed for
this spike.

## 7. USER ACTION REQUIRED — environment, Pixel, emulator, and installs

This is a future **human-run runbook**, not a record of actions already performed. The user performs
all IDE/SDK/emulator/device setup, starts the local PWA server, transfers fixtures, runs `adb`, and
installs, updates, or removes clients. The future agent may research, prepare artifacts and exact
commands, and diagnose the user’s redacted observations; it must not click installers, accept
licences, change Windows features or firmware, create/start an AVD, configure the Pixel, run `adb`,
start deployment, or install/remove a client for the user.

**Recommended WSL2 topology:** keep the repository and ordinary Linux development shell in WSL2,
but install and run Android Studio Stable, the Android SDK, Android Emulator, and the one selected
`adb.exe` on the **Windows host**. The Windows emulator uses the currently recommended Windows
Hypervisor Platform (WHPX), and Windows owns the normal USB/Google-driver path to the Pixel. Do not
install a second Linux Android Studio/emulator inside WSL2 or attach the Pixel to WSL with
`usbipd-win` merely to make paths look Linux-native: Microsoft documents that WSL USB attachment is
not native and requires additional host setup, while Android’s Linux emulator acceleration assumes
KVM access. An exception needs a dated official-source check, an explicit user decision, and a new
checkpoint before any setup change.

The WSL/Windows boundary is intentional:

- a production static server may run in WSL2; Windows normally reaches a WSL2 listener through
  `localhost`, and Windows `adb.exe reverse` then maps the Android target’s `localhost` to it;
- device discovery, fixture push, reverse mappings, and APK installation use only the Windows SDK’s
  `adb.exe`, even when the user invokes that executable through WSL interoperability;
- a Windows executable needs a Windows-readable artifact path. The future agent should translate a
  WSL path with `wslpath -w` and ask the user to validate it with read-only `Test-Path`; it must not
  move the repository, create a second checkout, install a second SDK, edit `PATH`, or stage files
  without user approval;
- if the eventual Android build cannot safely consume the user-selected SDK across this boundary,
  stop. The user chooses between a user-managed Windows build location and an explicitly approved
  WSL SDK; the agent does not silently create either.

### 7.1 Placeholders, local-only values, and command safety

The future agent fills artifact, version, package, hash, build-ID, and port placeholders it controls.
The user substitutes tool paths, serials, AVD names, and wireless endpoints privately in the local
terminal; those values are never sent back merely so the agent can render a command. Reject any
command that still contains a placeholder whose source or safe local substitution is unexplained.

| Placeholder | Source of value |
| --- | --- |
| `<ADB_WIN>` | Exact `adb.exe` path under Android Studio’s displayed **Android SDK Location**, normally in `platform-tools`; do not guess it from an old `PATH`. |
| `<EMULATOR_WIN>` | Exact `emulator.exe` path under the same SDK location. |
| `<WSL_DISTRO>` | Distribution name shown locally by `wsl.exe --list --quiet`; it is not needed in shared notes. |
| `<*_WSL_PATH>` | Absolute path in the WSL repository, supplied in §6. |
| `<*_WINDOWS_PATH>` | Windows-readable form validated locally with `Test-Path`; it may be a `\\wsl.localhost\...` path or a user-created Windows staging copy. |
| `<AVD_NAME>` | Name the user chose in Device Manager. |
| `<AVD_SERIAL>` / `<PHYSICAL_SERIAL>` / `<TARGET_SERIAL>` | Current value shown by the user’s private `adb devices -l` output. It is ephemeral routing data, not evidence to share. |
| `<FROZEN_*>` | Exact version/API/revision from the agent’s dated compatibility sheet; never substitute “latest” after the freeze. |
| `<HOST_PORT>` | Loopback port on which the user starts the supplied production server in WSL2. |
| `<DEVICE_PORT>` | Port selected by the agent for the target-side `localhost` URL; it may equal `<HOST_PORT>`. |
| `<FIXTURE_FILENAME>` / `<FIXTURE_SHA256>` | Synthetic fixture basename and hash in §6’s manifest. |
| `<PACKAGE_ID>` / `<APK_SHA256>` / `<BUILD_ID_1>` / `<BUILD_ID_2>` | Per-arm values in §6’s checksummed manifest. |
| `<PAIR_HOST>`, `<PAIR_PORT>`, `<DEBUG_HOST>`, `<DEBUG_PORT>` | Values displayed transiently by the Pixel’s Wireless debugging screen. |

Command blocks are **templates**, not commands executed by this plan. Run Windows templates in a
normal, non-administrator PowerShell unless a documented Windows feature/driver step explicitly
opens an elevated system dialog. Run WSL templates in the existing WSL shell. Quote every path.
Before each command that changes a target, re-read the serial and the intended target name. Except
for discovery (`devices -l`, `version`) and wireless `pair`/`connect`, every `adb` template uses
`-s <TARGET_SERIAL>`; do not use a bare `adb install`, `adb push`, `adb reverse`, `adb uninstall`,
`-d`, `-e`, or a persistent `ANDROID_SERIAL` shortcut.

Keep serials, RSA fingerprints, pairing codes, device/Wi-Fi IP addresses, Windows/WSL user names,
account names, and personally identifying command output in the local terminal only. Never paste
them into shared notes, chat, screenshots, commits, or returned evidence. Pairing codes must be
entered only into `adb`’s interactive prompt, not placed on a command line or in shell history.

### 7.2 Preflight inventory and topology decision record

1. **Pause for the agent’s read-only inventory request.** The agent should ask the user to inspect,
   not change: Windows edition/build and CPU architecture, WSL version/distribution, available RAM
   and free disk, Task Manager’s virtualization state, existing Android Studio channel/version,
   Android SDK Location, installed SDK packages, existing AVDs, and all discoverable `adb.exe`
   copies. Do not uninstall, update, or “repair” anything during inventory.
2. **Locate tools without changing `PATH`.** If Android Studio already opens, use **Settings →
   Languages & Frameworks → Android SDK** (wording can vary) as the authority for the SDK Location.
   The user may run these read-only PowerShell checks locally (keep distribution names private):

   ```powershell
   wsl.exe --version
   wsl.exe --list --verbose
   Get-Command adb.exe -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
   Test-Path -LiteralPath "<ADB_WIN>"
   & "<ADB_WIN>" version
   Test-Path -LiteralPath "<EMULATOR_WIN>"
   ```

   More than one result is a warning, not an instruction to delete anything. Record the exact
   selected executable and use it consistently; mixing Windows and WSL Platform-Tools can create
   competing ADB servers or route the phone into the wrong environment.
3. **Detect path interoperability read-only.** In WSL, translate one synthetic artifact path:

   ```bash
   wslpath -w "<FIXTURE_WSL_PATH>"
   ```

   In PowerShell, keep the returned value private and check it:

   ```powershell
   Test-Path -LiteralPath "<FIXTURE_WINDOWS_PATH>"
   ```

   If it is `False`, or if the selected Windows tool later rejects the UNC path, stop. The user may
   choose a temporary Windows staging directory and copy only checksummed synthetic/build artifacts
   there, then re-hash them. The agent must not create that directory or copy files itself.
4. **Record the network boundary without reconfiguring it.** Later, when a server exists, Windows
   must be able to open `http://localhost:<HOST_PORT>` before `adb reverse` is attempted. Do not
   enable mirrored networking, add a firewall rule, bind publicly, discover a WSL IP, or create a
   tunnel during preflight.
5. **Write a local decision record** containing only non-sensitive facts: `Windows host Android
   toolchain + WSL2 source/server`, selected Studio channel, selected SDK location (redact user-name
   segments before sharing), selected `adb.exe`, intended USB-first Pixel path, and whether an
   existing installation can be reused. Include a reason for every exception.

**Checkpoint 7-A — topology frozen:** proceed only when the user confirms the Windows-host topology,
one selected Windows `adb.exe`, adequate resources against the current official requirements, and a
Windows-readable synthetic path. Return only `PASS/STOP`, tool versions, and redacted path shapes;
do not return raw inventory output.

### 7.3 Windows virtualization prerequisites — inspect first, never automate firmware

1. Open **Task Manager → Performance → CPU** and read **Virtualization**. If it says **Enabled**,
   continue. If it says **Disabled**, stop before creating an AVD. Do not let an agent, script, or
   installer change UEFI/BIOS settings.
2. If firmware virtualization is disabled, consult the computer manufacturer’s current instructions
   for that exact model and prepare any required BitLocker/device-encryption recovery material
   before entering firmware. The user alone decides whether to enable Intel VT-x/VMX or AMD-V/SVM.
   No generic key sequence is safe enough for this plan. If this is a managed machine, obtain the
   administrator’s approval instead of bypassing policy.
3. In **Turn Windows features on or off**, inspect **Windows Hypervisor Platform**. Android’s current
   emulator guidance recommends WHPX on Windows. If unchecked, the user may choose to enable that
   one feature and reboot when Windows requests it. Do not disable Hyper-V, Virtual Machine
   Platform, WSL, security software, Memory Integrity, or another hypervisor speculatively; WSL2
   itself depends on Windows virtualization components.
4. After the selected Android Emulator component exists, the user may run the documented
   acceleration diagnostic from non-administrator PowerShell:

   ```powershell
   & "<EMULATOR_WIN>" -accel-check
   ```

   Keep the raw hardware output local; report only `acceleration supported` or the redacted error
   category. A failure returns to the official acceleration/troubleshooting pages. Do not download a
   legacy hypervisor driver or change firmware based on an undated blog.

**Checkpoint 7-B — acceleration ready:** `Virtualization: Enabled`, WHPX available, required reboot
complete, and the emulator acceleration check succeeds. If any item fails, use the physical Pixel
only if the experiment owner accepts the missing emulator gate; otherwise stop.

### 7.4 Install Android Studio Stable on the Windows host

1. From the official Android Studio install page, verify the current Windows requirements and that
   this CPU architecture is supported. Download the current **Stable** Windows installer from the
   official Android domain. Do not select Preview, Beta, Canary, a third-party mirror, or a bundled
   download site. Record the installer filename, advertised version, URL, and access date; do not
   publish local download paths.
2. Close unrelated applications and launch the installer personally. Leave **Android Studio**
   selected. Select **Android Virtual Device/Emulator** support when offered. Do not install an
   HAXM-era accelerator, NDK, CMake, LLDB, extra device families, or preview SDK because a generic
   wizard recommends more than the freeze sheet.
3. Start Android Studio and use **Standard** only if its component summary matches this runbook;
   otherwise use **Custom** to inspect each component and SDK location. Do not import stale settings
   from an unrelated installation unless the inventory explicitly approved reuse.
4. Read each licence and accept only the licences for the selected Android SDK/emulator components.
   A licence failure is a stop, not permission for the agent to run `sdkmanager --licenses`.
5. Reopen Android Studio once. Record the complete Studio Stable version/build, bundled runtime
   version, and displayed Android SDK Location. Do not add global environment variables merely to
   make `adb` shorter; templates use the exact path.

**Checkpoint 7-C — IDE opens:** Android Studio Stable reaches its Welcome window without an update
or setup error, and the SDK Location is known. Do not open/build the prototype yet.

### 7.5 Freeze versions, then select exact SDK Manager components

The agent must first provide a dated compatibility sheet derived from the frozen Angular/Ionic/
Capacitor/AGP/Kotlin versions. It supplies values for the placeholders below; the user must not
invent API numbers or select whatever is newest on the day of installation.

1. Open **Tools → SDK Manager** from a project, or **More Actions → SDK Manager** from the Welcome
   window. Confirm that **Android SDK Location** is the location recorded at Checkpoint 7-C.
2. On **SDK Platforms**, enable **Show Package Details** and select exactly:
   - **Android SDK Platform `<FROZEN_COMPILE_API>`**; and
   - system-image package **`<FROZEN_SYSTEM_IMAGE_API>` / `<IMAGE_FLAVOR>` /
     `<IMAGE_ARCH>`** only if Device Manager has not already queued that exact image.
3. On **SDK Tools**, enable **Show Package Details** and select exactly the sheet’s required entries:
   - **Android SDK Platform-Tools `<FROZEN_PLATFORM_TOOLS_VERSION>`** — contains `adb.exe`;
   - **Android SDK Build-Tools `<FROZEN_BUILD_TOOLS_VERSION>`**;
   - **Android Emulator `<FROZEN_EMULATOR_VERSION>`**;
   - **Android SDK Command-line Tools `<FROZEN_COMMAND_LINE_TOOLS_VERSION>`** only when the build
     compatibility sheet requires it; and
   - **Google USB Driver `<FROZEN_GOOGLE_USB_DRIVER_VERSION>`** only if the physical-Pixel checks in
     §7.9 show that Windows needs it.
4. Leave unchecked: preview/extension platforms not named by the sheet, obsolete packages, NDK,
   CMake, LLDB, HAXM, Android Auto/TV/Wear/Google Play Games images, and extra system images. A Google
   APIs image supplies Google APIs; a Play Store-labelled image additionally supplies Play Store
   access and is release-key signed. Select a Play Store image only if the frozen Chrome/PWA test
   requires its bundled/updatable Chrome path.
5. Review Android Studio’s proposed changes before pressing **Apply**. If any package or revision is
   not on the sheet, cancel and ask the agent to reconcile it. The user accepts licences and waits
   for completion.
6. Reopen SDK Manager and capture a text inventory of component names/revisions (not a screenshot
   containing local paths). The agent should adapt build commands to these recorded versions; it
   must not update them mid-trial.

**Checkpoint 7-D — SDK frozen:** every required component/revision is installed, no preview package
was substituted, and `<ADB_WIN>` resolves inside the selected SDK’s `platform-tools` directory.

### 7.6 Create and verify one Pixel 7 Pro-equivalent AVD

1. Open **Device Manager → Create Virtual Device → Phone**. Select the built-in **Pixel 7 Pro**
   hardware profile if present. If absent, stop and have the agent record the available profiles;
   choose the nearest built-in Pixel by display size/density only after recording the mismatch.
   Do not create a custom profile and call it Pixel 7 Pro-equivalent without listing every changed
   property.
2. Select the exact frozen system image: API `<FROZEN_SYSTEM_IMAGE_API>`, architecture
   `<IMAGE_ARCH>`, and `<IMAGE_FLAVOR>` (`Google APIs` or `Google Play`) from §7.5. Do not choose a
   preview image. If it is not offered for the hardware profile, return to the compatibility sheet
   rather than silently changing API or ABI.
3. Name it `<AVD_NAME>`, for example a non-sensitive pattern containing `Docparse`, `Pixel7Pro`, the
   frozen API, and image flavor. Keep orientation, RAM, internal storage, VM heap, graphics, camera,
   network, and boot settings at Device Manager defaults unless the agent has documented a test
   requirement. Record any non-default value.
4. Finish creation, then inspect **Edit this AVD → Show Advanced Settings** once without changing it.
   Record hardware profile, API, image flavor/ABI, graphics mode, RAM/storage, and whether snapshots
   are enabled.
5. Start the AVD from Device Manager. Complete only minimal setup. Do not add a personal Google
   account, restore a backup, enable cloud sync, or place real data in it. If a Play image requires
   an account solely to update Chrome, stop and decide whether the bundled Chrome can be frozen or a
   disposable test account is justified; never use a personal account by default.
6. Wait for the launcher to settle. In the AVD, record **Settings → About emulated device → Android
   version** and Chrome’s **Settings → About Chrome → Application version**. Do not update either
   after recording unless the compatibility sheet explicitly changes and the whole baseline is
   re-frozen.
7. In private PowerShell, discover the current emulator serial and verify it before doing anything
   target-changing:

   ```powershell
   & "<ADB_WIN>" devices -l
   & "<ADB_WIN>" -s "<AVD_SERIAL>" get-state
   & "<ADB_WIN>" -s "<AVD_SERIAL>" shell getprop ro.product.model
   & "<ADB_WIN>" -s "<AVD_SERIAL>" shell getprop ro.build.version.sdk
   ```

   Expected: one intended emulator row in state `device`, the expected model/profile, and the frozen
   API. The serial can change and stays private.
8. Cold-boot once from Device Manager’s AVD menu and repeat the verification. If Quick Boot and cold
   boot produce different failures, record that fact; do not wipe data yet.

**Checkpoint 7-E — AVD baseline:** the AVD boots twice, reports `device`, matches the selected
profile/API/image, Chrome opens, and no personal account or real data exists on it.

### 7.7 Use one Platform-Tools installation and select every target explicitly

1. Before each test block, close any WSL/Linux `adb` server and use only `<ADB_WIN>`. Do not use
   `sudo adb`. If another Android tool has started a different `adb.exe`, stop and reconcile it
   before installation rather than repeatedly killing servers during a test.
2. Run discovery locally:

   ```powershell
   & "<ADB_WIN>" version
   & "<ADB_WIN>" devices -l
   ```

   Classify each intended row as `device`, `offline`, or `unauthorized`. Never infer “the only row”
   will stay the intended target.
3. For each AVD/Pixel command, replace `<TARGET_SERIAL>` locally and first run:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" get-state
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" shell getprop ro.product.model
   ```

   Read the model on screen. Abort if it does not match the target named in the handoff.
4. Keep emulator and Pixel command blocks separate. Never reuse a copied command until its serial,
   package ID, path, and intended operation have all been re-read.

**Checkpoint 7-F — routing safe:** one Windows Platform-Tools revision is in use, each intended
target is `device`, and the user can distinguish the AVD from Pixel without sharing either serial.

### 7.8 Transfer and verify the synthetic fixture on the AVD

1. Obtain `<FIXTURE_WSL_PATH>`, `<FIXTURE_FILENAME>`, byte size, and `<FIXTURE_SHA256>` from §6.
   Confirm the document is visibly synthetic. If the hash or watermark is absent, stop; never
   substitute a real tax/family document.
2. Validate the Windows-readable path and host hash in PowerShell:

   ```powershell
   Test-Path -LiteralPath "<FIXTURE_WINDOWS_PATH>"
   Get-FileHash -Algorithm SHA256 -LiteralPath "<FIXTURE_WINDOWS_PATH>"
   ```

   Compare all 64 hexadecimal characters to `<FIXTURE_SHA256>`. A mismatch stops transfer.
3. Reconfirm the AVD model, then push only this file:

   ```powershell
   & "<ADB_WIN>" -s "<AVD_SERIAL>" get-state
   & "<ADB_WIN>" -s "<AVD_SERIAL>" shell getprop ro.product.model
   & "<ADB_WIN>" -s "<AVD_SERIAL>" push "<FIXTURE_WINDOWS_PATH>" "/sdcard/Download/<FIXTURE_FILENAME>"
   ```

4. If the image provides `sha256sum`, verify the device copy; if it does not, record `device hash
   tool unavailable` and rely on host hash, transferred byte count, and the prototype’s later
   content hash instead of installing another utility:

   ```powershell
   & "<ADB_WIN>" -s "<AVD_SERIAL>" shell sha256sum "/sdcard/Download/<FIXTURE_FILENAME>"
   ```

5. In the AVD, open **Files → Downloads**, confirm the expected filename/size, and open the PDF.
   Confirm the watermark and close it. Do not upload it to Drive or another provider.

**Checkpoint 7-G — AVD fixture ready:** host hash matches, transfer completed to the intended AVD,
and Files opens the visibly synthetic PDF.

### 7.9 Prepare the physical Pixel 7 Pro and authorise USB debugging

1. **Back up before changing settings.** On the Pixel, open **Settings → Google services → Backup**
   or the current equivalent, review which categories are backed up, and decide whether to run a
   backup. Photos/contacts and third-party apps can have separate backup mechanisms. The user—not
   the experiment—chooses the account and confirms any backup completed. Never report account names,
   backup contents, or timestamps in shared notes.
2. Record a baseline locally: Pixel model, Android version/API, OS build, Android security update,
   Chrome application version, free storage, battery level, screen-lock presence, and whether a
   work profile/device-management policy is active. Share only versions and coarse readiness. Do
   not update Android, Google Play system, Chrome, or apps unless the user explicitly elects a new
   baseline; if anything updates, repeat and re-freeze the baseline.
3. Confirm the explicit exclusions: no bootloader unlock, **OEM unlocking**, root, factory reset,
   beta OS, account removal, security-control bypass, or real-document access is required. If an
   instruction asks for one, stop.
4. On Pixel, open **Settings → About phone → Build number**, tap it seven times, and authenticate to
   expose Developer options. Then open **Settings → System → Developer options** (the exact nesting
   can vary) and enable **USB debugging** only. Leave OEM unlocking and all other developer toggles
   unchanged.
5. Use a known data-capable cable directly to the Windows computer where possible. Unlock the Pixel,
   connect it, and watch for the USB-debugging RSA prompt caused by this connection. Confirm the
   prompt appeared only after connecting this workstation and inspect its fingerprint locally.
   Reject any surprise prompt. Leave **Always allow from this computer** unchecked when the UI
   permits, then approve the current session. USB file-transfer mode is not required for ADB.
6. In private PowerShell, run:

   ```powershell
   & "<ADB_WIN>" devices -l
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" get-state
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" shell getprop ro.product.model
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" shell getprop ro.build.version.sdk
   ```

   Expected: Pixel row state `device`, model `Pixel 7 Pro`, and the recorded API. Never send the raw
   row to the agent; report `Pixel 7 Pro: device` plus versions only.
7. **Driver branch, only if Windows does not enumerate the Pixel:** first try another known-good
   data cable and USB port, keep the phone unlocked, reconnect, and inspect Windows Device Manager.
   If the device is missing or warning-marked, follow Android’s official OEM USB driver page. For a
   Google device, select the **Google USB Driver** through SDK Manager only if needed, then use
   Windows Device Manager’s **Update driver → Browse my computer** and point it to the SDK’s
   `extras\google\usb_driver` directory. Do not use a third-party driver site or driver updater.
   Reconnect and repeat step 6. Do not apply Linux `udev`, `plugdev`, `sudo adb`, or `usbipd-win`
   instructions to this recommended Windows-host path.

**Checkpoint 7-H — Pixel USB ready:** backup decision recorded, baseline frozen, the Pixel is
unlocked and listed as `device` through the selected Windows `adb.exe`, and only USB debugging was
enabled. `unauthorized`, `offline`, or no row is a stop handled in §7.16.

### 7.10 Transfer and verify the synthetic fixture on the Pixel

1. Repeat the host `Test-Path` and SHA-256 check from §7.8 immediately before transfer.
2. Reconfirm `Pixel 7 Pro`, then push the fixture explicitly:

   ```powershell
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" get-state
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" shell getprop ro.product.model
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" push "<FIXTURE_WINDOWS_PATH>" "/sdcard/Download/<FIXTURE_FILENAME>"
   & "<ADB_WIN>" -s "<PHYSICAL_SERIAL>" shell sha256sum "/sdcard/Download/<FIXTURE_FILENAME>"
   ```

   If `sha256sum` is unavailable, use the same non-installing fallback as §7.8. Do not switch to a
   cloud-backed picker or copy a real document.
3. On Pixel, open **Files → Downloads**, inspect filename/size, open the PDF, and confirm the obvious
   synthetic watermark. If Files selects a cloud provider, navigate back to local Downloads.

**Checkpoint 7-I — Pixel fixture ready:** the checksummed synthetic PDF opens from local Downloads,
and no real or cloud document was exposed.

### 7.11 Optional wireless debugging with pairing-code hygiene

USB is preferred for this short experiment. Use wireless debugging only if USB is already verified
or the user records why a cable is impractical.

1. Put Windows and Pixel on the same trusted private network. Do not use public, guest, hotel, or an
   untrusted corporate network; do not alter firewall/router settings or expose/forward an ADB port.
2. On Pixel open **Developer options → Wireless debugging**, enable it, and choose **Pair device with
   pairing code**. Keep the screen away from recordings/screen sharing. Pairing host/port and debug
   host/port can differ and can rotate.
3. From private PowerShell run the selected Windows ADB pair command **without the code in the
   command**. Type the short-lived code only at ADB’s interactive prompt and do not save it:

   ```powershell
   & "<ADB_WIN>" pair "<PAIR_HOST>:<PAIR_PORT>"
   ```

   If the command does not prompt interactively, cancel it; do not put the code after the address.
4. Connect using the separate debug endpoint shown by the phone, then discover its current serial:

   ```powershell
   & "<ADB_WIN>" connect "<DEBUG_HOST>:<DEBUG_PORT>"
   & "<ADB_WIN>" devices -l
   ```

5. Re-run the model/get-state checks with the new `<PHYSICAL_SERIAL>`. Use that exact serial on every
   later command. Keep USB connected if stability matters; do not assume the USB and Wi-Fi serials
   are interchangeable.

**Checkpoint 7-J — optional Wi-Fi ready:** pairing succeeded on a trusted private network and the
Wi-Fi row is `device`. Otherwise disable Wireless debugging and continue over USB or stop.

### 7.12 Serve, reverse, install, and update the PWA on one explicit target

Repeat this section first for the AVD and later for the Pixel; never map both accidentally. The user
must already have §6’s production-output path, exact WSL server command, `<HOST_PORT>`,
`<DEVICE_PORT>`, manifest ID/name, expected Chrome version, and `<BUILD_ID_1>`/`<BUILD_ID_2>`. `ng
serve`, a public host, an IP-LAN URL, a third-party tunnel, and a development build are not valid
substitutes.

1. In WSL, inspect the supplied command and start the production static server personally. It should
   bind to loopback (`127.0.0.1`) unless the documented WSL localhost bridge requires a narrowly
   approved alternative. Confirm its output identifies the production directory and `<HOST_PORT>`;
   leave this terminal open.
2. Before touching ADB, verify from **Windows PowerShell** that Windows can reach the WSL server:

   ```powershell
   Invoke-WebRequest -UseBasicParsing "http://localhost:<HOST_PORT>/"
   ```

   Expected: the PWA response, not another local service. If this fails, stop and use §7.16; do not
   bind to all interfaces, add a firewall exception, or substitute a private IP casually.
3. Reconfirm the target model, create one target-specific reverse mapping, and inspect it:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" get-state
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" shell getprop ro.product.model
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse "tcp:<DEVICE_PORT>" "tcp:<HOST_PORT>"
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse --list
   ```

   The device URL is now `http://localhost:<DEVICE_PORT>/`. `localhost` is important: Chrome treats
   it as a trustworthy local origin for service-worker/PWA testing. Do not replace it with the
   phone, Windows, or WSL IP.
4. On the selected target, open Chrome Stable manually and enter the exact device URL. Confirm
   `<BUILD_ID_1>`, manifest name/icon, fixture-free landing state, and no certificate/interstitial or
   remote-network request. Do not continue if another app/site answers.
5. Use Chrome’s current menu, normally **More → Add to home screen → Install app** (wording can
   vary). Choose the install action, not **Create shortcut**. If Chrome offers only a shortcut, stop
   and follow §7.16 rather than counting it as an installed PWA.
6. Close the source browser tab. Launch from the new launcher/app-drawer entry. Confirm the expected
   name/icon, standalone display, `<BUILD_ID_1>`, offline shell after one completed load, and—where
   the arm claims it—the expected `Docparse <letter>` Web Share Target in Files’ PDF share sheet.
   Do not select a personal file while inspecting the share sheet.
7. For the update trial, leave the installed PWA and its site data intact. Stop build 1’s server only
   through its documented terminal action, then personally start the supplied production server for
   `<BUILD_ID_2>` on the same origin/ports and with the same frozen manifest identity. Repeat the
   Windows localhost and reverse-list checks.
8. Follow the agent’s predeclared service-worker update script exactly: note the starting build ID,
   close all PWA windows, relaunch/navigate the installed app as instructed, accept only an expected
   in-app update prompt, and record every reload/relaunch until `<BUILD_ID_2>` appears. Because a
   waiting service worker may not control an existing page immediately, stale build 1 on the first
   launch is evidence, not permission to clear storage.
9. Stop after the scripted attempt count. Do not uninstall, clear Chrome/site data, use DevTools
   “Update on reload,” or force-stop before scoring; those actions invalidate update-friction data.

**Checkpoint 7-K — PWA path complete per target:** Windows localhost works, only the intended target
has the reverse mapping, Chrome performs an install rather than a shortcut, launcher/standalone and
share-target checks are recorded, and the scripted build-ID update has a factual result.

### 7.13 Verify, install, and update each APK by explicit serial

Do this separately for the Ionic and native arms, AVD before Pixel. The user must have §6’s package
ID, APK WSL/Windows path, byte size, SHA-256, signer/build ID, minimum API, and expected update-data
behaviour before starting.

1. Validate path, size, and checksum in Windows PowerShell:

   ```powershell
   Test-Path -LiteralPath "<APK_WINDOWS_PATH>"
   Get-Item -LiteralPath "<APK_WINDOWS_PATH>" | Select-Object Name,Length
   Get-FileHash -Algorithm SHA256 -LiteralPath "<APK_WINDOWS_PATH>"
   ```

   Compare the complete SHA-256 to `<APK_SHA256>`. Filename resemblance is not verification. A
   missing path, wrong byte count, or one-character hash difference is an immediate stop.
2. Re-read target, package, and operation; verify target model one last time:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" get-state
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" shell getprop ro.product.model
   ```

3. For a clean install, run only the exact checksummed artifact:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" install "<APK_WINDOWS_PATH>"
   ```

   Require `Success`. On Pixel, unlock and read any Android security confirmation; do not disable
   Play Protect or another security control to force success. ADB installation does **not** require
   enabling global **Install unknown apps**. If the user deliberately chooses Files-based sideload
   instead, grant that one source temporarily and revoke it immediately, but record that as a
   different distribution path.
4. Launch from the app drawer, verify package display name and `<BUILD_ID_1>`, perform only the
   familiarisation data-state check, and close it. Do not grant an unexpected permission.
5. Before update, verify build 2’s filename, byte size, and full checksum separately. Confirm that
   package ID and signing identity are expected to match, then run:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" install -r "<APK_BUILD_2_WINDOWS_PATH>"
   ```

   `-r` requests replacement while retaining app data. Require `Success`, launch from the existing
   icon, verify `<BUILD_ID_2>`, and record whether the declared state was retained.
6. On `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, signature mismatch, version downgrade, parse error,
   storage error, security-policy block, wrong build ID, or lost data, stop. Do not add `-d`,
   uninstall to make room, clear data, change package/signing configuration, or try random flags;
   return the redacted error category to the agent.

**Checkpoint 7-L — APK path complete per arm/target:** both full checksums matched, clean install and
`install -r` targeted the intended serial, build IDs are correct, and update-data behaviour is
recorded without bypassing a security control.

### 7.14 Expected permissions and mandatory stop conditions

1. Expected app runtime permission prompts: **none**. The PDF picker and inbound share use a
   user-selected document plus narrow `content://` URI grants. A packaged web client may declare the
   normal manifest `INTERNET` permission, which is not a runtime prompt. USB-debugging RSA,
   Chrome-PWA installation, and system picker UI are setup/system consent, not app permissions.
2. Deny and stop that arm if it requests camera, contacts, location, microphone, nearby devices,
   notifications, phone/SMS, accessibility service, device administration, VPN, media library,
   broad storage, **Manage all files**, or any permission not named in §6. Photograph or transcribe
   only the permission wording/app name after ensuring no notification, account, serial, or personal
   content is visible.
3. Also stop immediately for: checksum mismatch; wrong target/model/package/build ID; unexpected
   public/network upload; personal account/file shown; Chrome certificate/security warning;
   request to weaken Play Protect, screen lock, firewall, firmware, or device management; repeated
   crash/reboot; hot or low-battery phone; unexpected OS/app update; missing backup decision; or an
   instruction requiring root/OEM unlock/factory reset.
4. A stop is evidence. Preserve the target state, remove the cable if safety requires it, and report
   a redacted category. Do not “fix forward” in a way that destroys the clean-install/update trial.

### 7.15 Evidence the user returns to the agent

After every checkpoint, return a short, manually redacted report—not terminal dumps or screenshots
by default:

1. Checkpoint ID and `PASS`, `STOP`, or `NOT RUN`, with local date/time and one-sentence reason.
2. Windows version family/build, Studio Stable version/build, Java runtime version, and the exact
   installed SDK Platform/Platform-Tools/Build-Tools/Emulator/image revisions.
3. Topology decision (`Windows Android toolchain; WSL2 source/server`), whether Windows localhost
   reached the WSL server, and only a redacted SDK/artifact path shape.
4. AVD profile, API, image flavor/ABI, Chrome version, cold-boot result, and state `device`—never its
   serial.
5. Pixel model, Android/API/security-update and Chrome versions, backup decision (`reviewed`/
   `completed`/`declined` without account details), and USB/Wi-Fi state `device`—never its serial,
   RSA fingerprint, IP, pairing endpoint, or code.
6. Fixture filename, byte size, expected/observed SHA-256, target, and whether local Files opened the
   visible synthetic watermark. The synthetic hash is shareable; local paths are not.
7. Per arm/target: artifact filename, expected/observed SHA-256, package/manifest name, build IDs,
   install/update result and elapsed steps, data-retention result, PWA install-versus-shortcut,
   standalone/share-target result, and any permission wording.
8. Redacted error category and the exact checkpoint where work stopped. Remove user names, device
   identifiers, `content://` authorities, absolute paths, account/profile names, notifications,
   Wi-Fi details, personal filenames, and unrelated process/device rows before sharing.

**Checkpoint 7-M — evidence sufficient:** the agent can reproduce the setup decision and evaluate
results from versions, hashes, statuses, and build IDs without receiving secrets, identifiers, IPs,
or personally identifying output.

### 7.16 Troubleshooting decision tree — diagnose narrowly, then stop or re-checkpoint

Start at the observed symptom. Make one branch’s checks in order; after any change, return to the
relevant checkpoint. Do not combine speculative fixes.

1. **`adb devices -l` shows no devices:**
   - Confirm the command is the selected Windows `<ADB_WIN>`, not Linux `adb`, and its version is the
     frozen Platform-Tools version.
   - **AVD:** confirm Device Manager says the intended AVD is running and its launcher completed;
     cold-boot once. If it did not boot, follow the virtualization branch.
   - **Pixel:** unlock it; verify USB debugging remains on; replace the cable/port with known data-
     capable ones; inspect Windows Device Manager; then follow the official Google USB driver branch
     in §7.9. Do not apply Linux permissions or use `usbipd-win` for this topology.
   - If still absent, stop and return `no Windows ADB enumeration` plus versions—not raw identifiers.
2. **Pixel is `unauthorized`:**
   - Unlock the Pixel and look for the RSA dialog. Reject it if it was not triggered by this
     workstation; otherwise approve without selecting persistent trust when possible.
   - If no dialog appears, disconnect/reconnect once. The user may choose **Developer options →
     Revoke USB debugging authorizations**, then reconnect and approve a fresh key; this revokes all
     previously trusted computers and must be recorded.
   - Do not delete host `adbkey` files or repeatedly toggle unrelated developer settings. If it
     remains unauthorized, stop.
3. **Target is `offline`:**
   - Wait for Android to finish booting, unlock it, and reconnect the cable or disable/re-enable only
     Wireless debugging as appropriate.
   - Close Android Studio/device tools, ensure no install/update is active, then the user may restart
     the selected ADB server once:

     ```powershell
     & "<ADB_WIN>" kill-server
     & "<ADB_WIN>" start-server
     & "<ADB_WIN>" devices -l
     ```

   - This affects every attached target. Re-discover all serials afterward. If still offline, cold-
     boot the AVD or return to USB; do not continue deployment.
4. **Emulator will not start or reports missing acceleration:**
   - Re-run `<EMULATOR_WIN> -accel-check`; verify Task Manager virtualization, WHPX selection, reboot
     completion, free RAM/Windows commit, and free disk against current official requirements.
   - Close conflicting VM-heavy applications, but do not disable WSL/Hyper-V/security software or
     edit firmware automatically. If firmware is disabled, return to the manufacturer/user decision
     in §7.3. If graphics fails after acceleration passes, use Android’s emulator troubleshooting
     page and record any proposed non-default graphics setting before changing it.
5. **Windows cannot reach the WSL production server:**
   - Confirm the server is still running in WSL, uses the supplied production directory and port,
     and WSL itself can open `http://localhost:<HOST_PORT>`.
   - Repeat Windows `Invoke-WebRequest`. Check for a port collision or server bound to a different
     port. Do not expose `0.0.0.0`, add a firewall rule, switch WSL networking mode, or use a tunnel
     without a separate user-approved plan. Stop if Windows localhost forwarding remains blocked.
6. **`adb reverse` fails or the device page will not load:**
   - Reconfirm target state/model and that `<DEVICE_PORT>`/`<HOST_PORT>` match the handoff; inspect
     `reverse --list` for that serial.
   - Confirm Windows itself gets the expected page. Remove only the stale mapping for the intended
     target, then add it once:

     ```powershell
     & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse --remove "tcp:<DEVICE_PORT>"
     & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse "tcp:<DEVICE_PORT>" "tcp:<HOST_PORT>"
     ```

   - In target Chrome use exactly `http://localhost:<DEVICE_PORT>/`. If it still fails, stop; do not
     substitute a network IP/public host.
7. **Chrome offers only Create shortcut, not Install app:**
   - Confirm Chrome Stable/version, exact localhost origin, successful reverse, production build,
     manifest link/name/icons/start URL/display/id, and absence of manifest/service-worker errors.
   - Confirm an app with the same manifest identity is not already installed. Remove an old test PWA
     only before the scored baseline and only after recording it; never remove it during the update
     trial.
   - Spend the required user interaction/time if current Chrome install criteria call for it, then
     check the menu again. If only a shortcut remains, record `PWA not installable` and stop that
     arm; do not score the shortcut as equivalent.
8. **Installed PWA remains on `<BUILD_ID_1>`:**
   - Confirm build 2 is served from the identical origin and manifest identity, Windows sees build
     2, the reverse mapping remains, and all old PWA windows were closed as scripted.
   - Repeat only the predeclared relaunch/reload count. Do not clear storage, unregister the service
     worker, or reinstall before evidence is captured. Report the stale version as the result.
9. **APK install/update fails:**
   - Recheck complete hash, byte size, target model/API/free storage, package ID, signing expectation,
     and redacted ADB error category.
   - Never solve update incompatibility with `-d`, uninstall, data clear, signature changes, or
     security bypass during the trial. Return the error to the agent for a rebuilt artifact.

### 7.17 Complete teardown, revocation, and local cleanup

Teardown happens only after exports/evidence are safely captured or immediately if security requires
it. Execute it separately for each serial and keep the serial private.

1. Stop the WSL production server with its documented graceful terminal action. For each target,
   inspect then remove only this experiment’s reverse mapping:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse --list
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" reverse --remove "tcp:<DEVICE_PORT>"
   ```

   Do not use a target-ambiguous command or remove unrelated mappings.
2. On each target, uninstall the PWA from its launcher/App info or Chrome’s installed-app UI and
   confirm its launcher entry is gone. Clear only that localhost site’s data if the evidence plan
   requires it; do not clear all Chrome data or personal browsing data.
3. Uninstall each APK by exact target and package only after recording/exporting its evidence:

   ```powershell
   & "<ADB_WIN>" -s "<TARGET_SERIAL>" uninstall "<PACKAGE_ID>"
   ```

   Confirm `Success` and that the app icon is gone. A missing/changed package ID is a stop, not a
   reason to list or remove unrelated packages.
4. Delete `<FIXTURE_FILENAME>` from local Downloads on the AVD and Pixel using Files, then empty no
   broader recycle/bin location. Delete any user-created Windows staging copies and temporary build
   artifacts only after their evidence hashes are recorded. Keep the repository’s canonical
   synthetic fixture.
5. On Pixel, if wireless debugging was used, disconnect the private endpoint locally, turn
   **Wireless debugging** off, and use its paired-devices screen to forget this workstation:

   ```powershell
   & "<ADB_WIN>" disconnect "<DEBUG_HOST>:<DEBUG_PORT>"
   ```

6. With the USB cable disconnected, open **Developer options**, choose **Revoke USB debugging
   authorizations**, turn **USB debugging** off, then turn **Use developer options** off. Accept a
   Pixel restart if requested. Reconnect once only if the user wants to verify that ADB no longer
   authorises; do not approve the new prompt.
7. Revoke any per-source **Install unknown apps** grant if Files-based sideload was used. Confirm no
   personal account was added to the AVD. Wipe/delete the disposable AVD through Device Manager if
   no rerun is planned; otherwise leave it powered off with its synthetic data removed and record
   that it remains.
8. Stop the selected ADB server after all targets are detached:

   ```powershell
   & "<ADB_WIN>" kill-server
   ```

9. Do **not** disable firmware virtualization, WHPX, WSL, Hyper-V, Windows security, drivers, Android
   Studio, or SDK components as routine teardown; those are host-level shared dependencies. Any
   removal is a separate user decision using official uninstall guidance.
10. Return only teardown statuses: mappings removed, PWA/APKs removed, fixture/staging copies
    removed, wireless pairing forgotten, USB authorizations revoked, debugging/developer options
    off, AVD deleted or powered off, and ADB server stopped. Do not return serials/endpoints.

**Checkpoint 7-N — teardown complete:** no test client, reverse mapping, fixture copy, wireless pair,
or Pixel debugging authorization remains; shared host tooling is unchanged unless the user made a
separate removal decision.

## 8. Joint HITL evaluation on the Pixel 7 Pro

The agent facilitates and records; the user touches the phone and supplies subjective judgement.
Do not substitute emulator screenshots for this session.

### 8.1 Familiarisation (unscored)

For each frozen A/B/C build, user launches once, chooses the synthetic PDF once, shares it once,
and asks any clarification. Agent verifies build ID/event log and removes setup failures. Keep the
technology mapping hidden where practical.

### 8.2 Scored script

Run A/B/C in a randomised order. For each arm, user narrates confusion but receives no coaching:

1. Find the app from the launcher, cold-launch it, and trigger **Check fixture source now**.
2. Return Home with system Back and inspect whether progress/result language felt clear.
3. Open Android Files, find the fixture, Share it to the arm, verify metadata, and queue it.
4. Repeat through **Choose PDF**; deliberately cancel the picker once, then select the PDF.
5. Background to Files and return through Recents; rotate portrait→landscape→portrait once; use
   Back through receipt/review/home.
6. Enable airplane mode, remove the arm from Recents, relaunch, and run launcher trigger + picker
   against the local fixture. Restore connectivity afterward.
7. Run the prepared build-ID update path and identify the new version.
8. Export the event JSON. User rates the arm before proceeding; no technology reveal or cross-arm
   discussion yet.

After all arms, reveal A/B/C. Conduct a comparative interview:

- Which would you willingly keep installed for a family document workflow, and why?
- Did any install icon/surface feel like “just a website” or any packaged app feel foreign? Name
  the concrete interaction, not the framework reputation.
- Was Share from Files discoverable and trustworthy? Was picker fallback acceptable?
- Which install/update path would be acceptable for one household, five relatives, and public
  users?
- For the developer/operator, which unfamiliar concepts felt incidental setup versus recurring
  maintenance?

### 8.3 Evaluator safeguards

- One user on one Pixel is directional evidence, not a usability study.
- Capture the user’s words before showing timings, bundle sizes, implementation effort, or brand.
- Separate browser/OS bugs, setup friction, framework friction, and prototype bugs in notes.
- Do not award “feel” from screenshots or inferred native widgets; score observed interactions.
- Record fatigue/order effects and rerun only a clearly invalid trial, with the reason noted.

## 9. Evidence matrix, rubric, and decision rules

### 9.1 Raw evidence matrix

Complete cells with facts, links, measurements, or `not tested`—never marketing adjectives.

| Evidence | Angular PWA | Ionic + Angular | Kotlin + Compose |
| --- | --- | --- | --- |
| Frozen versions / build ID | | | |
| Time: scaffold → first render/build/emulator/Pixel | | | |
| Direct Angular/TypeScript/template/CSS reuse | | | |
| New platform concepts and native/config LOC | | | |
| Production-web/APK size and dependency count | | | |
| Clean install steps/prompts/time | | | |
| Build-ID update steps/prompts/time | | | |
| Launcher/source trigger | | | |
| Files direct-share PDF | | | |
| System picker fallback | | | |
| Wrong/multiple-file handling | | | |
| Runtime/manifest permissions | | | |
| Resume/rotation/Back result | | | |
| Offline shell + local journey | | | |
| Median cold launch → usable Home | | | |
| Median Share → usable Review | | | |
| Median picker → usable Review | | | |
| Pixel user ratings and verbatim notes | | | |
| Framework-specific store preparation | | | |
| Shared Play obligations / PWA hosting obligations | | | |
| Failures, workarounds, unresolved unknowns | | | |

Attach raw event JSON, checksums, command/timing log, permission/manifest dumps, dependency and size
reports, screenshots/recordings, evaluator sheet, and official-source ledger. Keep `out/` ignored;
commit only a redacted aggregate if the user later asks.

### 9.2 Scored rubric (100 points)

Score each 0–5 with one sentence pointing to raw evidence, then multiply by the weight.

| Criterion | Weight | 0 anchor | 3 anchor | 5 anchor |
| --- | ---: | --- | --- | --- |
| Angular skill reuse | 25 | None; most work requires a new language/toolchain | Angular concepts cover UI but recurring native/runtime work is material | Ordinary Angular workflow covers nearly all product work; platform delta is small and isolated |
| Phone-triggered ingestion | 30 | Cannot complete source trigger or obtain PDF | Source trigger + picker work; share needs friction/workaround or has lifecycle gaps | Launcher, direct share, and picker all work reliably with narrow access and clear recovery |
| Distribution/store friction | 20 | Test install/update is unreliable or release path has unresolved blockers | Reproducible local install/update; documented release work is material but understood | Reproducible low-step install/update and a credible low-overhead distribution route for target users |
| Feel on Pixel | 25 | User would not keep it; major navigation/responsiveness mismatch | Usable with noticeable roughness | User prefers/accepts it; launch, handoff, Back/resume, and feedback feel coherent |

For distribution, report two subscores before combining: **observed household test distribution**
and **documented public release obligations**. PWA hosting/browser installation and Android Play
publishing are different mechanisms, so “no store submission” must not erase HTTPS hosting,
install discoverability, browser support, update control, signing, policy, or support costs.

### 9.3 Hard gates and decision policy

An arm is **not viable for this MVP shape** if it:

- cannot trigger the source command and complete the system-picker PDF path on the physical Pixel;
- requires broad/all-files access, unexplained sensitive permission, or sending the test PDF to a
  third party;
- cannot be installed and updated reproducibly from checksummed artifacts/URL; or
- loses selected content silently or misreports a queue success.

Direct share is highly weighted evidence but not a hard gate because picker fallback may satisfy
the product; its absence must be explicit in the phone-ingestion score.

Only name a provisional leader when all three arms were run on the Pixel, none of the leader’s hard
gates failed, its weighted score leads by at least **10/100**, and the result stays ahead when each
category is varied by one rating point. Otherwise conclude **inconclusive** and name the smallest
follow-up that resolves the tied criterion. A hard-gate failure overrides totals. Also report an
unweighted table so chosen weights remain visible rather than masquerading as fact.

Do not turn this spike directly into an ADR. A recommendation must state target distribution
(household-only versus public), source-trigger semantics, browser/device limits, and confidence
from the single-device sample. Any claim about Play review time, iOS behaviour, long-term
maintenance, or general performance remains documentation-based/not tested unless separately
exercised.

## 10. Privacy, security, and non-goals

### Privacy constraints

- Use only the watermarked synthetic PDF. Existing prototype convention says real official
  documents are sensitive ([`prototypes/README.md`](../README.md)); a mobile screen recording,
  share sheet, exported URI, and cloud-backed picker can leak more than file contents alone.
- No real names, addresses, tax IDs, account IDs, Google Drive folder, personal screenshots, auth
  tokens, analytics, crash reporting, remote fonts, public tunnel, or third-party upload.
- Log fixture basename, MIME, byte count, synthetic hash, build ID, state, and relative timing only.
  Strip `content://` authorities, absolute paths, device serials, Wi-Fi addresses, notifications,
  and account names before an artifact is committed/shared.
- Keep processing in memory and discard selected bytes after hash/receipt. Clear app/site data and
  uninstall after testing. Debug APKs and local HTTP are acceptable only on the trusted test path,
  never as a production security design.
- The prototype should ask for no runtime permission. A browser/system picker or transient URI
  grant is the intended least-privilege mechanism; unexpected requests stop the arm for review.

### Deliberately OUT of scope

- production client architecture, shared component extraction, final framework selection, or ADR;
- actual Google Drive/folder connector, gateway, ingestion worker, auth provider, REST contract,
  upload/retry/background sync, multi-user/client association, or notifications;
- parsing, OCR, translation, AI, Confidence, document display, manual fill-in, Q&A, or obligations;
- camera/scanner capture (the MVP Document is a text-based PDF), gallery/media access, multiple
  documents, document-tree access, or all-files access;
- iOS, tablets/foldables beyond one rotation check, accessibility audit beyond labelled controls,
  battery profiling, broad device/browser matrix, production performance benchmark, or security
  audit;
- Play account creation, fees, store listing, production signing keys, AAB upload, internal/closed
  track, review, or publication; the spike records current first-party requirements only;
- Trusted Web Activity, Bubblewrap, React Native, Flutter, Kotlin Multiplatform, or a fourth arm.

## 11. First-party source starting set for the next session

These links are the **research queue**, not findings. The next agent must open the current pages,
record access dates/versions, follow changed canonical links, and verify behaviour hands-on. Do not
convert a support table or framework claim into this prototype’s conclusion.

### Angular PWA and installed-web path

- Angular service-worker/PWA setup: <https://angular.dev/ecosystem/service-workers/getting-started>
  (if the current canonical route has moved, use Angular’s current docs rather than silently
  relying on the v17 archive).
- Angular CLI deployment/production output: <https://angular.dev/tools/cli/deployment>
- W3C Web App Manifest specification: <https://www.w3.org/TR/appmanifest/>
- Chrome install criteria: <https://web.dev/articles/install-criteria>
- Chrome for Android web-app installation steps:
  <https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid>
- Chrome Web Share Target guide:
  <https://developer.chrome.com/docs/capabilities/web-apis/web-share-target>
- Web Share Target draft/specification: <https://w3c.github.io/web-share-target/>

Questions to settle: current Angular production-service-worker workflow; secure-context/local-host
behaviour on this Pixel; installed share-target registration; `multipart/form-data` PDF delivery,
service-worker lifecycle, offline replay, file-size limits, browser/version dependence, and update
semantics.

### Ionic Angular and Capacitor Android

- Ionic Angular overview/version support: <https://ionicframework.com/docs/angular/overview>
- Ionic Angular quickstart: <https://ionicframework.com/docs/angular/quickstart>
- Capacitor environment requirements:
  <https://capacitorjs.com/docs/getting-started/environment-setup>
- Capacitor Android lifecycle/build surface: <https://capacitorjs.com/docs/android>
- Capacitor Android plugin guide (including intent bridges):
  <https://capacitorjs.com/docs/plugins/android>
- Capacitor Android manifest/configuration:
  <https://capacitorjs.com/docs/android/configuration>
- Capacitor Filesystem API: <https://capacitorjs.com/docs/apis/filesystem>
- Capacitor outbound Share API (consult specifically to avoid assuming it receives shares):
  <https://capacitorjs.com/docs/apis/share>

Questions to settle: compatible Angular/Ionic/Capacitor/Android versions; whether a maintained
first-party inbound-share API exists; minimum custom Kotlin/Java bridge for `ACTION_SEND` and
`content://`; URI lifetime across resume; WebView/offline behaviour; and native-project maintenance
that ordinary Angular changes would incur.

### Native Android, file ingress, and feel baseline

- Jetpack Compose setup: <https://developer.android.com/develop/ui/compose/setup>
- Receive shared data in Compose:
  <https://developer.android.com/develop/ui/compose/sharing/receive>
- Android receiving simple data/files (including PDF MIME guidance):
  <https://developer.android.com/training/sharing/receive>
- Storage Access Framework PDF picker:
  <https://developer.android.com/training/data-storage/shared/documents-files>
- Minimise permission requests:
  <https://developer.android.com/privacy-and-security/minimize-permission-requests>
- Core Android app quality checks:
  <https://developer.android.com/docs/quality-guidelines/core-app-quality>
- Android launch timing terminology:
  <https://developer.android.com/topic/performance/vitals/launch-time>

Questions to settle: current recommended Activity Result/Compose APIs; MIME and grant flags for one
PDF; cold/warm intent handling; Back/resume/rotation; permission-free SAF access; and which native
defaults should remain unmodified as the feel baseline.

### User setup, emulator, local serving, and distribution friction

- Install Android Studio (including Windows requirements):
  <https://developer.android.com/studio/install>
- Select and update exact SDK Manager packages:
  <https://developer.android.com/studio/intro/update>
- Create/manage Android Virtual Devices:
  <https://developer.android.com/studio/run/managing-avds>
- Run the Android Emulator: <https://developer.android.com/studio/run/emulator>
- Configure Windows emulator acceleration/WHPX:
  <https://developer.android.com/studio/run/emulator-acceleration>
- Troubleshoot the Android Emulator:
  <https://developer.android.com/studio/run/emulator-troubleshooting>
- Run on a hardware device (USB/Wi-Fi and Linux setup):
  <https://developer.android.com/studio/run/device>
- Configure on-device Developer options and USB debugging:
  <https://developer.android.com/studio/debug/dev-options>
- Install the Google/OEM USB driver on Windows when needed:
  <https://developer.android.com/studio/run/oem-usb>
- Android Debug Bridge and RSA/wireless debugging: <https://developer.android.com/tools/adb>
- ADB reverse port forwarding to a local server:
  <https://developer.android.com/develop/ui/views/layout/webapps/access-local-server>
- Chrome local-PWA testing and Android localhost forwarding:
  <https://web.dev/learn/pwa/tools-and-debug>
- Chrome service-worker lifecycle/update behavior:
  <https://developer.chrome.com/docs/workbox/service-worker-lifecycle>
- Chrome web-app manifest identity during updates:
  <https://developer.chrome.com/docs/capabilities/pwa-manifest-id>
- Pixel backup/restore guidance:
  <https://support.google.com/pixelphone/answer/7179901>
- Microsoft WSL interoperability and Windows-readable Linux paths:
  <https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop>
- Microsoft WSL networking and Windows-to-WSL localhost forwarding:
  <https://learn.microsoft.com/en-us/windows/wsl/networking>
- Microsoft’s documented extra setup required to attach USB devices to WSL2:
  <https://learn.microsoft.com/en-us/windows/wsl/connect-usb>
- Build debug APKs/release artifacts: <https://developer.android.com/build/build-for-release>
- Play create/setup obligations:
  <https://support.google.com/googleplay/android-developer/answer/9859152>
- Play release/testing tracks:
  <https://support.google.com/googleplay/android-developer/answer/9859348>
- New personal-account testing requirements:
  <https://support.google.com/googleplay/android-developer/answer/14151465>
- Play target API requirement:
  <https://developer.android.com/google/play/requirements/target-sdk>
- Play Data safety declaration:
  <https://support.google.com/googleplay/android-developer/answer/10787469>

Questions to settle: actual host prerequisites, stable SDK/API selected by frozen framework versions,
Pixel/AVD connectivity, localhost PWA installation, debug artifact install/update steps, and the
current difference between measured household distribution and untested public-store obligations.

## 12. Next-session order of work

1. Re-read this plan, `CONTEXT.md`, ADR-0002, and `prototypes/README.md`; confirm that the issue’s
   acceptance criteria have not changed, without commenting on issue #5.
2. Complete Gate 0: official-source/version ledger, compatibility freeze, experiment sheet, and
   privacy review.
3. Inventory only; present the user with the exact missing items from §7. Stop for user Android
   Studio/SDK/AVD and Pixel-debugging actions.
4. After `adb devices` and the AVD are user-confirmed, create fixture/common acceptance contract.
5. Build to parity in this order: Angular PWA → Ionic Angular/Capacitor → Kotlin/Compose. The order
   tests Angular reuse directly; it does not predetermine evaluation order or winner.
6. Run automated checks and Gate 3 on the AVD; timebox direct-share work equally.
7. Produce §6 checksummed handoff. User installs and performs Gate 4 familiarisation on Pixel.
8. Freeze/randomise builds, run joint HITL §8, export evidence, and reveal A/B/C.
9. Complete raw matrix, rubric, sensitivity/hard-gate analysis, limitations, and provisional result
   (leader or inconclusive). Keep researched store facts separate from observed install evidence.
10. Only in a separately requested follow-up: publish findings to issue #5 and propose any research
    note/ADR. This plan itself neither modifies the issue nor recommends a client shape.

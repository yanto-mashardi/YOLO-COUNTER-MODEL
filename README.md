# YOLO Counter Model — Windows prototype

Validation-first local inference for BIMA2, no new VPS process. Windows x64, Python 3.12, PyTorch 2.7.1 CPU or CUDA 12.6, Ultralytics 8.3.203, OpenCV, Tkinter. NVIDIA driver and internet needed for GPU and initial weights. Review Ultralytics AGPL/enterprise license for intended deployment; no weights bundled. Only load trusted .pt files.

## Install
Download repository ZIP, extract to a local folder (not Google Drive), run INSTALL.bat, choose GPU or CPU. If Python is missing the installer uses winget and asks to reopen CMD. Run START.bat after success. Installer runs pip check and four pure Python tests; Windows and live camera tests not yet executed.

## Workflow
Two independent panels, one per port. Paste the RTSP URL from BIMA2 Manager (validation account for tests), or choose a local video. Choose YOLOv8/YOLO11 n/s/m or trusted custom .pt with COCO vehicle labels. Set confidence, IoU, input resolution, tracker, device, normalized line endpoints, crossing direction. A directed finite line counts bottom-center crossing once per track. Positive direction is positive signed cross product (horizontal left-to-right line means downward in image). Trucks/buses are provisionally grouped as mobil; motorcycle as motor. Validate with actual port classification before commissioning. Bounding boxes, IDs, line, counts and effective FPS are displayed. No automatic restart on stream loss; gap/restart may cause missed or duplicate crossings, requiring manual reconciliation. No frame retention by default.

## Publishing
Default VALIDATION uses isolated SQLite run and never contacts VPS. OPERATIONAL requires live RTSP, separate per-port token and exact device label from Manager plus explicit confirmation. Ensure only one instance per port, stop previous sender, drain backlog, record local baseline (zero for fresh official DB), configure Manager and then start official run. Daily raw counts reset at midnight WIB. Existing official database survives normal restart; reconcile after loss, camera movement, tracker restart or changed configuration. Snapshots on crossings and every 10 seconds; resume endpoint determines server cutoff/cursor. POST /api/vehicles/{port} with Bearer token and OBSERVED payload, WIB date/time, cumulative mobil/motor. Only server ACK is shown as accepted; local snapshots retained for retry. No test/simulated data sent automatically. BIMA2 remains responsible for stock/outflow/ML2. No automatic sending after user closes the app. Final pending rows may require restart and manual reconciliation. Do not run two instances on one official database. Tokens are entered per session, never committed. Plain RTSP is not encrypted; restrict network access where possible.

## Archive and validation
Export CSV to selected folder, including Google Drive Desktop synchronized folder if configured. Unique filenames by device, port and export time; no deletion or overwrite. Export is manual in this version. Compare manual counts vs model counts over identical recorded video/time windows, report absolute error and WAPE per class, throughput and gap durations. Do not activate official publishing until acceptance test passes. Suggested thresholds are project decisions (e.g. WAPE <= 5% and no duplicate crossings in test). Validation clips use processing clock in this prototype, not original event time. Automatic manual-count scoring, background service/auto reconnect, secure saved profiles and scheduled Drive archive are follow-up features, not yet implemented.

## Acceptance tests
1. CPU and GPU install, CUDA availability and actual inference.
2. Both RTSP streams simultaneously, line direction and tracking.
3. Manual count comparison in congestion, low light, mixed vehicles.
4. Confirm validation never posts; use isolated test backend or approved official commissioning for end-to-end test.
5. Token rejected on wrong port; resume after network interruption; midnight rollover; handover baseline preserved; compare stock on BIMA2.
6. Confirm local CSV and Drive sync without changing AIS archive.

## Interactive counting line
Before Start, choose local video or RTSP, click Atur garis hitung pada video, click two endpoints on the captured frame, use Balik arah masuk to orient the arrow, and save. Coordinates are normalized; preview does not run inference or publish data. Operational mode requires calibration for the current source in the current session. Local video is reopened at its beginning when Start is pressed. Calibration is in memory only; persistence and polygon ROI remain future work. Stop before editing. Windows GUI testing pending.

## Detection ROI
Use Atur area deteksi & garis hitung. Select two opposite corners of the green ROI, then draw the yellow counting line inside it and choose direction. Inference/tracking receives only the crop; coordinates are translated back to the full image for crossing. Outside is dimmed in preview. A source change resets ROI and invalidates calibration. Keep sufficient space on both sides of the counting line for tracking. Counting diagnostics print raw detector label, voted group and both counters before/after. ROI is session-only. Fixed model input size means CPU speedup is not guaranteed. Actual video validation remains required.

## Manual-start update
Terminal tabs with Monitoring, Konfigurasi and Validasi. Save local profile without RTSP credentials or publisher tokens; mode defaults to Validation. Recalibrate after source changes. Headless skips preview rendering. Manual count evaluation saves WAPE CSV. Validation RTSP reconnects automatically; Operational stops on source loss pending reconciliation (automatic operational reconnect not yet safe). Operational archive writes separate daily raw-counter CSVs every 60 seconds and on graceful stop, refuses conflicting existing archives. Choose Google Drive Desktop folder manually. Read-only BIMA2 authorization check; end-to-end official test pending. No Windows autostart. Windows GUI and runtime testing pending.

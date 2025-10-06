09:59:23 - INFO - Windows long path support: ENABLED
09:59:23 - INFO - Windows long path support: ENABLED
2025-10-06 09:59:23,824 - FolderStructureUtility - INFO - Windows long path support: ENABLED
2025-10-06 09:59:23,825 - FolderStructureUtility - INFO - Windows long path support: ENABLED
2025-10-06 10:01:03,781 - FolderStructureUtility - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 1
10:01:03 - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 1
10:01:14 - INFO - Cleared all items
2025-10-06 10:01:14,451 - FolderStructureUtility - INFO - Cleared all items
2025-10-06 10:02:19,360 - FolderStructureUtility - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 2
10:02:19 - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 2
10:02:26 - INFO - Cleared all items
2025-10-06 10:02:26,876 - FolderStructureUtility - INFO - Cleared all items
2025-10-06 10:03:30,112 - core.services.resource_management_service - DEBUG - Tracked resource 1a99e115-af6c-41a3-be3e-508d91944382 for BatchController_2149630190160
2025-10-06 10:03:30,112 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker batch_processor_100330 with ID 1a99e115-af6c-41a3-be3e-508d91944382
2025-10-06 10:03:30,114 - BatchController - INFO - [BatchController] batch_processing_started - 2 jobs
2025-10-06 10:03:30,118 - core.services.resource_management_service - INFO - Registered component: WorkflowController_2147933691280 (type: controller)
2025-10-06 10:03:30,118 - WorkflowController - INFO - [WorkflowController] process_forensic_workflow - files: 0, folders: 1
2025-10-06 10:03:30,118 - ValidationService - INFO - [ValidationService] validate_form_data
2025-10-06 10:03:30,118 - ValidationService - INFO - [ValidationService] form_data_valid
2025-10-06 10:03:30,118 - ValidationService - INFO - [ValidationService] validate_file_paths - 1 paths
2025-10-06 10:03:30,119 - ValidationService - INFO - [ValidationService] file_paths_validated - 1 valid paths
2025-10-06 10:03:30,119 - PathService - INFO - [PathService] build_forensic_path - base: E:\Move Copy Test Results
2025-10-06 10:03:30,915 - PathService - INFO - [PathService] template_path_built - E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:03:30,959 - core.services.resource_management_service - DEBUG - Tracked resource 2e535d68-3fd5-4971-a328-27d754cd7097 for WorkflowController_2147933691280
2025-10-06 10:03:30,959 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker forensic_workflow_100330 with ID 2e535d68-3fd5-4971-a328-27d754cd7097
2025-10-06 10:03:30,959 - WorkflowController - INFO - [WorkflowController] workflow_thread_created - destination: E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - === ANALYSIS START ===
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - Total items to process: 1
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - is_same_drive flag: None
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - Destination: E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - Processing item: type=folder, path=E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1, relative=None
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO - >>> FOLDER ITEM DETECTED <<<
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO -   Path exists: True
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO -   Path value: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO -   Checking is_same_drive: None
2025-10-06 10:03:30,961 - core.workers.folder_operations - INFO -   ✗ DIFFERENT DRIVES - Exploding folder into files
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO -   Exploded into 98 individual files
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - === ANALYSIS COMPLETE ===
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - Total files: 98
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - Folder items (for instant move): 0
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - Empty dirs: 43
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - Analysis errors: 0
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - === EXECUTION PHASE START ===
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO - Received from analysis:
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO -   total_files: 98
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO -   folder_items: 0
2025-10-06 10:03:31,023 - core.workers.folder_operations - INFO -   empty_dirs: 43
2025-10-06 10:03:34,925 - core.workers.folder_operations - INFO - No folders for same-drive move optimization
2025-10-06 10:03:35,013 - FolderStructureUtility - DEBUG - Same filesystem detected: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1\Comparisons For Presentation - Copy Test\21-330359 YRP Evidence of K. Caesar Compare and Contrast Report.pdf and E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time (device: 2261293896)
2025-10-06 10:03:35,013 - FolderStructureUtility - INFO - MOVE MODE SELECTED:
  Reason: Same filesystem detected
  Source device: 2261293896
  Dest device: 2261293896
  Files: 98
  User setting: auto_move
2025-10-06 10:03:35,013 - FolderStructureUtility - INFO - Starting MOVE operation: 98 items to E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:03:35,015 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (261): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:35,016 - FolderStructureUtility - DEBUG - Using long path support for move: 21-330359 YRP Evidence of K. Caesar Compare and Contrast Report.pdf
10:03:35 - INFO - MOVE MODE SELECTED:
  Reason: Same filesystem detected
  Source device: 2261293896
  Dest device: 2261293896
  Files: 98
  User setting: auto_move
10:03:35 - INFO - Starting MOVE operation: 98 items to E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:03:35,206 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (260): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:35,207 - FolderStructureUtility - DEBUG - Using long path support for move: 21-65481 YRP Evidence of K. Caesar Compare and Contrast Report.pdf
2025-10-06 10:03:36,703 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (251): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:36,704 - FolderStructureUtility - DEBUG - Using long path support for move: YRP Evidence of K. Caesar Compare and Contrast Report.pdf
2025-10-06 10:03:39,035 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (265): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,037 - FolderStructureUtility - DEBUG - Using long path support for move: ~$idence of K. Caesar Compare and Contrast Report Final-2.docx
2025-10-06 10:03:39,056 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (286): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,058 - FolderStructureUtility - DEBUG - Using long path support for move: Evidence of K. Caesar Compare and Contrast Report Final.pdf
2025-10-06 10:03:39,171 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (277): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,172 - FolderStructureUtility - DEBUG - Using long path support for move: email thread with ECKO UNLTD.pdf
2025-10-06 10:03:39,200 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (269): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,201 - FolderStructureUtility - DEBUG - Using long path support for move: Additional Request.pdf
2025-10-06 10:03:39,250 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (272): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,252 - FolderStructureUtility - DEBUG - Using long path support for move: Request for Service 1.PDF
2025-10-06 10:03:39,274 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (273): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:39,276 - FolderStructureUtility - DEBUG - Using long path support for move: Dominion Cam 40.pdf
2025-10-06 10:03:46,489 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (285): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:46,491 - FolderStructureUtility - DEBUG - Using long path support for move: Exemplar Reenactment Cam 11.pdf
2025-10-06 10:03:53,473 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (284): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:53,475 - FolderStructureUtility - DEBUG - Using long path support for move: Exemplar Reenactment Cam 9.pdf
2025-10-06 10:03:53,610 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (276): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:53,612 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 1.pdf
2025-10-06 10:03:54,488 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (276): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:54,490 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 6.pdf
2025-10-06 10:03:54,619 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (276): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:54,621 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 7.pdf
2025-10-06 10:03:56,381 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (287): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:56,382 - FolderStructureUtility - DEBUG - Using long path support for move: Dominion - Technical Report.pdf
2025-10-06 10:03:56,495 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (318): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:56,496 - FolderStructureUtility - DEBUG - Using long path support for move: Exemplar Reenactment - Peter Easton Pub - Technical Report.pdf
2025-10-06 10:03:56,560 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (295): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:56,562 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Pub - Technical Report.pdf
2025-10-06 10:03:56,613 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (266): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...
2025-10-06 10:03:56,614 - FolderStructureUtility - DEBUG - Using long path support for move: Request for Peer Review.pdf
2025-10-06 10:03:56,701 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (278): E:\Move Copy Test Results\PR98765 - Batch Move Test 1\Hooked @ 12345 Danforth Ave\28SEP25_0959_to_6O...

10:05:17 - INFO - MOVE operation completed: 98 items, 102.16s
2025-10-06 10:05:17,172 - FolderStructureUtility - INFO - MOVE operation completed: 98 items, 102.16s
2025-10-06 10:05:17,189 - core.resource_coordinators.worker_coordinator - DEBUG - Worker forensic_workflow_100330 finished after 106.23s
2025-10-06 10:05:17,189 - core.services.resource_management_service - DEBUG - Released resource 2e535d68-3fd5-4971-a328-27d754cd7097 for WorkflowController_2147933691280
10:05:17 - ERROR - File count mismatch: expected 0, got 98
2025-10-06 10:05:17,223 - FolderStructureUtility - ERROR - File count mismatch: expected 0, got 98
[2025-10-06 10:05:17] ERROR [core.error_handler:215] [FileOperationError] Job 2849c9e6-8dc0-4d32-9736-5034870b2801 failed file integrity validation | Context: stage=integrity_validation, job_id=2849c9e6-8dc0-4d32-9736-5034870b2801, worker_class=BatchProcessorThread, worker_object_name=BatchProcessorThread_2149628071936, thread_id=2149628071936, operation_name=Batch Processing (2 jobs), cancelled=False
NoneType: None
2025-10-06 10:05:17,223 - core.error_handler - ERROR - [FileOperationError] Job 2849c9e6-8dc0-4d32-9736-5034870b2801 failed file integrity validation | Context: stage=integrity_validation, job_id=2849c9e6-8dc0-4d32-9736-5034870b2801, worker_class=BatchProcessorThread, worker_object_name=BatchProcessorThread_2149628071936, thread_id=2149628071936, operation_name=Batch Processing (2 jobs), cancelled=False
NoneType: None
2025-10-06 10:05:17,223 - core.services.resource_management_service - INFO - Registered component: WorkflowController_2147933691280 (type: controller)
2025-10-06 10:05:17,224 - WorkflowController - INFO - [WorkflowController] process_forensic_workflow - files: 0, folders: 1
2025-10-06 10:05:17,224 - ValidationService - INFO - [ValidationService] validate_form_data
2025-10-06 10:05:17,224 - ValidationService - INFO - [ValidationService] form_data_valid
2025-10-06 10:05:17,224 - ValidationService - INFO - [ValidationService] validate_file_paths - 1 paths
2025-10-06 10:05:17,225 - ValidationService - INFO - [ValidationService] file_paths_validated - 1 valid paths
2025-10-06 10:05:17,225 - PathService - INFO - [PathService] build_forensic_path - base: E:\Move Copy Test Results
2025-10-06 10:05:17,248 - ErrorNotificationSystem - INFO - MANAGER: Showing new error notification error_0_f7337218
2025-10-06 10:05:17,248 - ErrorNotificationSystem - INFO - Creating notification error_0_f7337218 with message: 'File integrity validation failed. Some files may not have been copied correctly....'
2025-10-06 10:05:17,248 - ErrorNotificationSystem - DEBUG - Notification error_0_f7337218 severity: ErrorSeverity.ERROR
2025-10-06 10:05:17,254 - ErrorNotificationSystem - DEBUG - No auto-dismiss for error_0_f7337218 - severity: ErrorSeverity.ERROR
2025-10-06 10:05:17,264 - BatchController - INFO - [BatchController] batch_processing_completed
[2025-10-06 10:05:17] ERROR [core.error_handler:215] [FileOperationError] Job 2849c9e6-8dc0-4d32-9736-5034870b2801 failed file integrity validation | Context: component=batch_queue_widget, operation=batch_processing
NoneType: None
2025-10-06 10:05:17,285 - core.error_handler - ERROR - [FileOperationError] Job 2849c9e6-8dc0-4d32-9736-5034870b2801 failed file integrity validation | Context: component=batch_queue_widget, operation=batch_processing
NoneType: None
2025-10-06 10:05:17,285 - ErrorNotificationSystem - INFO - MANAGER: Showing new error notification error_1_061ea535
2025-10-06 10:05:17,285 - ErrorNotificationSystem - INFO - Creating notification error_1_061ea535 with message: 'File integrity validation failed. Some files may not have been copied correctly....'
2025-10-06 10:05:17,285 - ErrorNotificationSystem - DEBUG - Notification error_1_061ea535 severity: ErrorSeverity.ERROR
2025-10-06 10:05:17,287 - ErrorNotificationSystem - DEBUG - No auto-dismiss for error_1_061ea535 - severity: ErrorSeverity.ERROR
2025-10-06 10:05:17,350 - PathService - INFO - [PathService] template_path_built - E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:05:17,378 - core.services.resource_management_service - DEBUG - Tracked resource 29b960e6-b338-4508-a481-63ef2d0624d4 for WorkflowController_2147933691280
2025-10-06 10:05:17,378 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker forensic_workflow_100517 with ID 29b960e6-b338-4508-a481-63ef2d0624d4
2025-10-06 10:05:17,378 - WorkflowController - INFO - [WorkflowController] workflow_thread_created - destination: E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - === ANALYSIS START ===
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - Total items to process: 1
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - is_same_drive flag: None
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - Destination: E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - Processing item: type=folder, path=E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 2, relative=None
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO - >>> FOLDER ITEM DETECTED <<<
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO -   Path exists: True
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO -   Path value: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 2
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO -   Checking is_same_drive: None
2025-10-06 10:05:17,380 - core.workers.folder_operations - INFO -   ✗ DIFFERENT DRIVES - Exploding folder into files
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO -   Exploded into 98 individual files
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - === ANALYSIS COMPLETE ===
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - Total files: 98
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - Folder items (for instant move): 0
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - Empty dirs: 43
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - Analysis errors: 0
2025-10-06 10:05:17,422 - core.workers.folder_operations - INFO - === EXECUTION PHASE START ===
2025-10-06 10:05:17,423 - core.workers.folder_operations - INFO - Received from analysis:
2025-10-06 10:05:17,423 - core.workers.folder_operations - INFO -   total_files: 98
2025-10-06 10:05:17,423 - core.workers.folder_operations - INFO -   folder_items: 0
2025-10-06 10:05:17,423 - core.workers.folder_operations - INFO -   empty_dirs: 43
2025-10-06 10:05:21,514 - core.workers.folder_operations - INFO - No folders for same-drive move optimization
2025-10-06 10:05:21,612 - FolderStructureUtility - DEBUG - Same filesystem detected: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 2\Comparisons For Presentation - Copy Test\21-330359 YRP Evidence of K. Caesar Compare and Contrast Report.pdf and E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time (device: 2261293896)
2025-10-06 10:05:21,612 - FolderStructureUtility - INFO - MOVE MODE SELECTED:
  Reason: Same filesystem detected
  Source device: 2261293896
  Dest device: 2261293896
  Files: 98
  User setting: auto_move
2025-10-06 10:05:21,612 - FolderStructureUtility - INFO - Starting MOVE operation: 98 items to E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:05:21,615 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (262): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:21,616 - FolderStructureUtility - DEBUG - Using long path support for move: 21-330359 YRP Evidence of K. Caesar Compare and Contrast Report.pdf
10:05:21 - INFO - MOVE MODE SELECTED:
  Reason: Same filesystem detected
  Source device: 2261293896
  Dest device: 2261293896
  Files: 98
  User setting: auto_move
10:05:21 - INFO - Starting MOVE operation: 98 items to E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6OCT25_0959_DVR_Time
2025-10-06 10:05:21,796 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (261): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:21,797 - FolderStructureUtility - DEBUG - Using long path support for move: 21-65481 YRP Evidence of K. Caesar Compare and Contrast Report.pdf
2025-10-06 10:05:23,293 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (252): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:23,295 - FolderStructureUtility - DEBUG - Using long path support for move: YRP Evidence of K. Caesar Compare and Contrast Report.pdf
2025-10-06 10:05:25,728 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (266): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:25,730 - FolderStructureUtility - DEBUG - Using long path support for move: ~$idence of K. Caesar Compare and Contrast Report Final-2.docx
2025-10-06 10:05:25,777 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (287): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:25,778 - FolderStructureUtility - DEBUG - Using long path support for move: Evidence of K. Caesar Compare and Contrast Report Final.pdf
2025-10-06 10:05:25,966 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (278): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:25,967 - FolderStructureUtility - DEBUG - Using long path support for move: email thread with ECKO UNLTD.pdf
2025-10-06 10:05:26,014 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (270): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:26,015 - FolderStructureUtility - DEBUG - Using long path support for move: Additional Request.pdf
2025-10-06 10:05:26,058 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (273): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:26,059 - FolderStructureUtility - DEBUG - Using long path support for move: Request for Service 1.PDF
2025-10-06 10:05:26,093 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (274): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:26,094 - FolderStructureUtility - DEBUG - Using long path support for move: Dominion Cam 40.pdf
2025-10-06 10:05:29,188 - ErrorNotificationSystem - INFO - Details button clicked for notification error_1_061ea535
2025-10-06 10:05:33,336 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (286): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:33,338 - FolderStructureUtility - DEBUG - Using long path support for move: Exemplar Reenactment Cam 11.pdf
2025-10-06 10:05:40,383 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (285): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:40,384 - FolderStructureUtility - DEBUG - Using long path support for move: Exemplar Reenactment Cam 9.pdf
2025-10-06 10:05:40,471 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (277): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:40,473 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 1.pdf
2025-10-06 10:05:41,371 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (277): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:41,373 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 6.pdf
2025-10-06 10:05:41,496 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (277): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:41,497 - FolderStructureUtility - DEBUG - Using long path support for move: Peter Easton Cam 7.pdf
2025-10-06 10:05:43,264 - FolderStructureUtility - DEBUG - Path exceeds 248 chars (288): E:\Move Copy Test Results\PR98765 - Batch Move Test 2\Shoppers @ 12345 Bayview Ave\28SEP25_0959_to_6...
2025-10-06 10:05:43,266 - FolderStructureUtility - DEBUG - Using long path support for move: Dominion - Technical Report.pdf

2025-10-06 10:07:02,153 - FolderStructureUtility - INFO - MOVE operation completed: 98 items, 100.54s
2025-10-06 10:07:02,157 - core.resource_coordinators.worker_coordinator - DEBUG - Worker forensic_workflow_100517 finished after 104.78s
2025-10-06 10:07:02,157 - core.services.resource_management_service - DEBUG - Released resource 29b960e6-b338-4508-a481-63ef2d0624d4 for WorkflowController_2147933691280
10:07:02 - INFO - MOVE operation completed: 98 items, 100.54s
2025-10-06 10:07:02,198 - FolderStructureUtility - ERROR - File count mismatch: expected 0, got 98
[2025-10-06 10:07:02] ERROR [core.error_handler:215] [FileOperationError] Job b269ba7f-9340-4d16-a2d1-7ad7f9927d21 failed file integrity validation | Context: stage=integrity_validation, job_id=b269ba7f-9340-4d16-a2d1-7ad7f9927d21, worker_class=BatchProcessorThread, worker_object_name=BatchProcessorThread_2149628071936, thread_id=2149628071936, operation_name=Batch Processing (2 jobs), cancelled=False
NoneType: None
2025-10-06 10:07:02,198 - core.error_handler - ERROR - [FileOperationError] Job b269ba7f-9340-4d16-a2d1-7ad7f9927d21 failed file integrity validation | Context: stage=integrity_validation, job_id=b269ba7f-9340-4d16-a2d1-7ad7f9927d21, worker_class=BatchProcessorThread, worker_object_name=BatchProcessorThread_2149628071936, thread_id=2149628071936, operation_name=Batch Processing (2 jobs), cancelled=False
NoneType: None
10:07:02 - ERROR - File count mismatch: expected 0, got 98
2025-10-06 10:07:02,219 - ErrorNotificationSystem - INFO - MANAGER: Showing new error notification error_2_b59dbb2b
2025-10-06 10:07:02,219 - ErrorNotificationSystem - INFO - Creating notification error_2_b59dbb2b with message: 'File integrity validation failed. Some files may not have been copied correctly....'
2025-10-06 10:07:02,219 - ErrorNotificationSystem - DEBUG - Notification error_2_b59dbb2b severity: ErrorSeverity.ERROR
2025-10-06 10:07:02,222 - ErrorNotificationSystem - DEBUG - No auto-dismiss for error_2_b59dbb2b - severity: ErrorSeverity.ERROR
2025-10-06 10:07:02,233 - BatchController - INFO - [BatchController] batch_processing_completed
[2025-10-06 10:07:02] ERROR [core.error_handler:215] [FileOperationError] Job b269ba7f-9340-4d16-a2d1-7ad7f9927d21 failed file integrity validation | Context: component=batch_queue_widget, operation=batch_processing
NoneType: None
2025-10-06 10:07:02,233 - core.error_handler - ERROR - [FileOperationError] Job b269ba7f-9340-4d16-a2d1-7ad7f9927d21 failed file integrity validation | Context: component=batch_queue_widget, operation=batch_processing
NoneType: None
2025-10-06 10:07:02,234 - ErrorNotificationSystem - INFO - MANAGER: Showing new error notification error_3_f52bd7c9
2025-10-06 10:07:02,234 - ErrorNotificationSystem - INFO - Creating notification error_3_f52bd7c9 with message: 'File integrity validation failed. Some files may not have been copied correctly....'
2025-10-06 10:07:02,234 - ErrorNotificationSystem - DEBUG - Notification error_3_f52bd7c9 severity: ErrorSeverity.ERROR
2025-10-06 10:07:02,235 - ErrorNotificationSystem - DEBUG - No auto-dismiss for error_3_f52bd7c9 - severity: ErrorSeverity.ERROR
2025-10-06 10:07:02,290 - BatchController - INFO - [BatchController] batch_processing_completed
2025-10-06 10:07:02,290 - ui.components.batch_queue_widget - ERROR - Exception in batch success processing: 'function' object has no attribute 'user_message'
2025-10-06 10:07:02,290 - core.resource_coordinators.worker_coordinator - DEBUG - Worker batch_processor_100330 finished after 212.18s
2025-10-06 10:07:02,290 - core.services.resource_management_service - DEBUG - Released resource 1a99e115-af6c-41a3-be3e-508d91944382 for BatchController_2149630190160
2025-10-06 10:07:10,666 - ErrorNotificationSystem - INFO - Details button clicked for notification error_3_f52bd7c9

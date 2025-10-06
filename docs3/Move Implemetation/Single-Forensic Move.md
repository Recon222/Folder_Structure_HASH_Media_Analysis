 Single Move E Drive (External):

09:36:16 - INFO - Windows long path support: ENABLED
09:36:16 - INFO - Windows long path support: ENABLED
2025-10-06 09:42:36,738 - ui.tabs.forensic_tab - DEBUG - No source files/folders yet - skipping same-drive detection
2025-10-06 09:49:24,056 - FolderStructureUtility - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 1
09:49:24 - INFO - Added folder with 98 files: Move Copy Testing 7gb E Drive - 1
2025-10-06 09:49:51,142 - ForensicController - INFO - [ForensicController] phase_transition - None -> validation
2025-10-06 09:49:51,142 - ForensicController - INFO - [ForensicController] destination_preset - Using pre-set destination: E:\Move Copy Test Results
2025-10-06 09:49:51,142 - ForensicController - INFO - [ForensicController] phase_transition - validation -> files
2025-10-06 09:49:51,142 - WorkflowController - INFO - [WorkflowController] process_forensic_workflow - files: 0, folders: 1
2025-10-06 09:49:51,142 - ValidationService - INFO - [ValidationService] validate_form_data
2025-10-06 09:49:51,142 - ValidationService - INFO - [ValidationService] form_data_valid
2025-10-06 09:49:51,142 - ValidationService - INFO - [ValidationService] validate_file_paths - 1 paths
2025-10-06 09:49:51,143 - ValidationService - INFO - [ValidationService] file_paths_validated - 1 valid paths
2025-10-06 09:49:51,143 - PathService - INFO - [PathService] build_forensic_path - base: E:\Move Copy Test Results
2025-10-06 09:49:51,920 - PathService - INFO - [PathService] template_path_built - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:51,963 - core.services.resource_management_service - DEBUG - Tracked resource 4c4e9a44-a29c-4f89-b5d0-d7911f046ebe for WorkflowController_2448283681680
2025-10-06 09:49:51,963 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker forensic_workflow_094951 with ID 4c4e9a44-a29c-4f89-b5d0-d7911f046ebe
2025-10-06 09:49:51,963 - WorkflowController - INFO - [WorkflowController] workflow_thread_created - destination: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:51,963 - core.services.resource_management_service - DEBUG - Tracked resource ec044d1c-d5ed-4eb7-a572-e32914f69192 for ForensicController_2448283682384
2025-10-06 09:49:51,963 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker file_thread_094951 with ID ec044d1c-d5ed-4eb7-a572-e32914f69192
2025-10-06 09:49:51,963 - ForensicController - INFO - [ForensicController] forensic_processing_started - Files: 0, Folders: 1
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - === ANALYSIS START ===
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - Total items to process: 1
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - is_same_drive flag: True
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - Destination: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - Processing item: type=folder, path=E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1, relative=None
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO - >>> FOLDER ITEM DETECTED <<<
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO -   Path exists: True
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO -   Path value: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO -   Checking is_same_drive: True
2025-10-06 09:49:51,968 - core.workers.folder_operations - INFO -   ✓ SAME DRIVE - Adding to folder_items for instant move
2025-10-06 09:49:51,969 - core.workers.folder_operations - INFO -   folder_items before append: 0
2025-10-06 09:49:51,969 - core.workers.folder_operations - INFO -   folder_items after append: 1
2025-10-06 09:49:51,969 - core.workers.folder_operations - INFO -   Added: ('folder', E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1, None)
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO -   Scanned 98 files in folder for size calculation
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - === ANALYSIS COMPLETE ===
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - Total files: 0
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - Folder items (for instant move): 1
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - Empty dirs: 0
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - Analysis errors: 0
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - === EXECUTION PHASE START ===
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO - Received from analysis:
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO -   total_files: 0
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO -   folder_items: 1
2025-10-06 09:49:52,041 - core.workers.folder_operations - INFO -   empty_dirs: 0
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO - Same-drive optimization active: Moving 1 folders instantly
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO - === FOLDER MOVE DEBUG ===
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO -   Source folder: E:\Move Copy Test Sources E Drive\Move Copy Testing 7gb E Drive - 1
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO -   Source exists: True
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO -   Dest folder: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time\Move Copy Testing 7gb E Drive - 1
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO -   Dest exists: False
2025-10-06 09:49:52,042 - core.workers.folder_operations - INFO -   Dest parent: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,043 - core.workers.folder_operations - INFO -   Dest parent exists: False
2025-10-06 09:49:52,104 - core.workers.folder_operations - INFO -   Created parent directory: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,105 - core.workers.folder_operations - INFO -   Calling Win32 MoveFileExW API...
2025-10-06 09:49:52,105 - core.workers.folder_operations - INFO -     Attempt 1: Standard move (should be instant on same drive)...
2025-10-06 09:49:52,109 - core.workers.folder_operations - INFO - ✓ Instant move succeeded!
2025-10-06 09:49:52,114 - ForensicController - INFO - [ForensicController] phase_transition - files -> files_complete
2025-10-06 09:49:52,114 - ForensicController - INFO - [ForensicController] file_result_stored - Stored FileOperationResult directly
2025-10-06 09:49:52,114 - ForensicController - INFO - [ForensicController] operation_completed - File operation successful
2025-10-06 09:49:52,115 - ForensicController - INFO - [ForensicController] phase_transition - files_complete -> reports
2025-10-06 09:49:52,115 - ForensicController - INFO - [ForensicController] base_path_found - Using base_forensic_path from metadata: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,115 - ReportController - INFO - [ReportController] generate_reports_with_path_determination - Starting report generation with path determination
2025-10-06 09:49:52,115 - ReportController - INFO - [ReportController] base_forensic_path - Using base path: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,115 - PathService - INFO - [PathService] determine_documents_location - base_path: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,115 - PathService - INFO - [PathService] level_calculation - Total levels: 3, Target level: 1, Steps up: 1
2025-10-06 09:49:52,221 - PathService - INFO - [PathService] documents_location - Created at: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents
2025-10-06 09:49:52,221 - ReportController - INFO - [ReportController] documents_location - Documents will be placed at: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents
2025-10-06 09:49:52,221 - ReportController - INFO - [ReportController] generate_all_reports - output: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents
2025-10-06 09:49:52,221 - ReportService - INFO - [ReportService] generate_time_offset_report - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Time_Offset_Report.pdf
2025-10-06 09:49:52,221 - ReportService - INFO - [ReportService] output_directory_ensured - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents
2025-10-06 09:49:52,222 - ReportService - INFO - [ReportService] pdf_generator_initialized
2025-10-06 09:49:52,247 - ReportService - INFO - [ReportService] time_offset_report_generated - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Time_Offset_Report.pdf
2025-10-06 09:49:52,247 - ReportController - INFO - [ReportController] time_offset_report_generated - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Time_Offset_Report.pdf
2025-10-06 09:49:52,247 - ReportService - INFO - [ReportService] generate_technician_log - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Upload_Log.pdf
2025-10-06 09:49:52,247 - ReportService - INFO - [ReportService] output_directory_ensured - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents
09:49:52 - INFO - Found 7za.exe at: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe
2025-10-06 09:49:52,323 - ReportService - INFO - [ReportService] technician_log_generated - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Upload_Log.pdf
2025-10-06 09:49:52,323 - ReportController - INFO - [ReportController] upload_log_generated - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\Documents\Upload_Log.pdf
2025-10-06 09:49:52,323 - ReportController - INFO - [ReportController] report_generation_completed - 2 reports
2025-10-06 09:49:52,323 - ForensicController - INFO - [ForensicController] reports_generated - 2 reports created
2025-10-06 09:49:52,323 - ForensicController - INFO - [ForensicController] phase_transition - reports -> zip
2025-10-06 09:49:52,323 - ForensicController - INFO - [ForensicController] base_path_found - Using base_forensic_path from metadata: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time
2025-10-06 09:49:52,323 - PathService - INFO - [PathService] find_occurrence_folder - path: E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\Hooked Danforth @ 12345 Danforth Ave\28SEP25_0936_to_6OCT25_0936_DVR_Time, root: E:\Move Copy Test Results
2025-10-06 09:49:52,323 - PathService - INFO - [PathService] occurrence_folder_found - E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive
2025-10-06 09:49:52,324 - FolderStructureUtility - DEBUG - Built archive settings: method=native_7zip, level=root
2025-10-06 09:49:52,324 - core.services.resource_management_service - DEBUG - Tracked resource be8c5d1f-68dd-4688-b773-b80af7b5d0c7 for ForensicController_2448283682384
2025-10-06 09:49:52,324 - core.resource_coordinators.worker_coordinator - DEBUG - Tracking worker zip_thread_094952 with ID be8c5d1f-68dd-4688-b773-b80af7b5d0c7
2025-10-06 09:49:52,325 - core.resource_coordinators.worker_coordinator - DEBUG - Worker forensic_workflow_094951 finished after 0.36s
2025-10-06 09:49:52,326 - core.services.resource_management_service - DEBUG - Released resource 4c4e9a44-a29c-4f89-b5d0-d7911f046ebe for WorkflowController_2448283681680
2025-10-06 09:49:52,326 - core.resource_coordinators.worker_coordinator - DEBUG - Worker file_thread_094951 finished after 0.36s
2025-10-06 09:49:52,326 - core.services.resource_management_service - DEBUG - Released resource ec044d1c-d5ed-4eb7-a572-e32914f69192 for ForensicController_2448283682384
2025-10-06 09:49:52,326 - FolderStructureUtility - INFO - Found 7za.exe at: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe
2025-10-06 09:49:52,327 - FolderStructureUtility - DEBUG - Validating 7za.exe at: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe
09:49:52 - INFO - 7za.exe validation successful
09:49:52 - INFO - Native 7zip controller initialized successfully
09:49:52 - INFO - Binary: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe
09:49:52 - INFO - Threads: 24
09:49:52 - INFO - Initialized with native 7zip (high-performance mode)
2025-10-06 09:49:52,347 - FolderStructureUtility - INFO - 7za.exe validation successful
2025-10-06 09:49:52,347 - FolderStructureUtility - DEBUG - Version info: 7-Zip (a) 25.01 (x86) : Copyright (c) 1999-2025 Igor Pavlov : 2025-08-03

Usage: 7za <command> [<swi...
2025-10-06 09:49:52,353 - FolderStructureUtility - DEBUG - ForensicCommandBuilder initialized:
2025-10-06 09:49:52,353 - FolderStructureUtility - DEBUG -   CPU cores: 24
2025-10-06 09:49:52,353 - FolderStructureUtility - DEBUG -   System memory: 127.5 GB
2025-10-06 09:49:52,353 - FolderStructureUtility - DEBUG -   Optimal threads: 24
2025-10-06 09:49:52,353 - FolderStructureUtility - DEBUG -   Memory usage: 70%
2025-10-06 09:49:52,353 - FolderStructureUtility - INFO - Native 7zip controller initialized successfully
2025-10-06 09:49:52,354 - FolderStructureUtility - INFO - Binary: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe
2025-10-06 09:49:52,354 - FolderStructureUtility - INFO - Threads: 24
2025-10-06 09:49:52,354 - FolderStructureUtility - INFO - Initialized with native 7zip (high-performance mode)
2025-10-06 09:49:52,354 - PathService - INFO - [PathService] template_archive_name_built - PR123456 - Move Zip Analysis - E Drive Hooked Danforth @ 12345 Danforth Ave. Video Recovery.zip
2025-10-06 09:49:52,354 - FolderStructureUtility - DEBUG - Using template-based archive name: PR123456 - Move Zip Analysis - E Drive Hooked Danforth @ 12345 Danforth Ave. Video Recovery.zip
2025-10-06 09:49:52,354 - FolderStructureUtility - DEBUG - Using native 7zip for E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive
09:49:52 - INFO - Executing native 7zip: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe a -tzip... (full command in debug)
09:49:52 - INFO - Full command: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe a -tzip -mx0 -mmt24 -y -bb1 E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive Hooked Danforth @ 12345 Danforth Ave. Video Recovery.zip E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\*
2025-10-06 09:49:52,429 - FolderStructureUtility - DEBUG - Built 7zip command: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe a -tzip -mx0 -mmt24 -y -bb1 E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive Hooked Danforth @ 12345 Danforth Ave. Video Recovery.zip E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\*
2025-10-06 09:49:52,429 - FolderStructureUtility - INFO - Executing native 7zip: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe a -tzip... (full command in debug)
2025-10-06 09:49:52,429 - FolderStructureUtility - INFO - Full command: D:\Active Working Coding Projects\Folder Structure Multiple Versions\Folder_Structure_HASH_Media_Analysis\bin\7za.exe a -tzip -mx0 -mmt24 -y -bb1 E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive Hooked Danforth @ 12345 Danforth Ave. Video Recovery.zip E:\Move Copy Test Results\PR123456 - Move Zip Analysis - E Drive\*
09:54:07 - INFO - Native 7zip completed successfully in 0.00s
09:54:07 - INFO - Native 7zip Performance: 29.9 MB/s avg, 0/100 files, 255.61s duration
2025-10-06 09:54:07,962 - FolderStructureUtility - INFO - Native 7zip completed successfully in 0.00s
2025-10-06 09:54:07,966 - FolderStructureUtility - INFO - Native 7zip Performance: 29.9 MB/s avg, 0/100 files, 255.61s duration
2025-10-06 09:54:07,969 - ForensicController - INFO - [ForensicController] phase_transition - zip -> zip_complete
2025-10-06 09:54:07,969 - ForensicController - INFO - [ForensicController] zip_completed - Archives created successfully
2025-10-06 09:54:07,989 - core.resource_coordinators.worker_coordinator - DEBUG - Worker zip_thread_094952 finished after 255.67s
2025-10-06 09:54:07,989 - core.services.resource_management_service - DEBUG - Released resource be8c5d1f-68dd-4688-b773-b80af7b5d0c7 for ForensicController_2448283682384
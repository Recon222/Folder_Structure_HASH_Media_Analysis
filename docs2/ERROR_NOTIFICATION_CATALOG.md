# Error Notification Catalog: Complete User-Facing Error Guide

*Generated: August 26, 2024*  
*Based on: Comprehensive codebase analysis of nuclear error handling system*

## Overview

This document provides a complete catalog of all error notifications that users will now see through the new non-modal error notification system. These notifications replace the previous 67 modal QMessageBox dialogs with modern, non-blocking notifications that appear in the top-right corner of the application.

**Key Changes for Users:**
- **No more blocking modal dialogs** - Users can continue working while aware of errors
- **Severity-based color coding** - Visual distinction between error types
- **Auto-dismiss for non-critical errors** - INFO (5s), WARNING (8s), ERROR/CRITICAL (manual dismiss)
- **Detailed technical information on demand** - "Details" button for debugging
- **Consistent messaging** - Clear, actionable user guidance

---

## Error Notification System Architecture

### Visual Design
- **Location**: Top-right corner of application window
- **Size**: Maximum 400px wide, 80px height per notification
- **Stacking**: Multiple notifications stack vertically
- **Animation**: Slide-in from right, fade-out on dismiss

### Severity Levels & Visual Styling

#### 🔵 **INFO** - Blue Theme
- **Color**: `#2196F3` (Light Blue)
- **Auto-dismiss**: 5 seconds
- **Use case**: Successful operations, status updates
- **Border**: Thin blue left border
- **Icon**: Information symbol

#### 🟡 **WARNING** - Orange Theme  
- **Color**: `#FF9800` (Orange)
- **Auto-dismiss**: 8 seconds
- **Use case**: Non-critical issues, validation errors
- **Border**: Thin orange left border
- **Icon**: Warning triangle

#### 🔴 **ERROR** - Red Theme
- **Color**: `#F44336` (Red)
- **Auto-dismiss**: Manual only
- **Use case**: Operation failures, system errors
- **Border**: Thin red left border
- **Icon**: Error X symbol

#### 🟣 **CRITICAL** - Purple Theme
- **Color**: `#9C27B0` (Purple)
- **Auto-dismiss**: Manual only (30 second timeout planned)
- **Use case**: Data integrity issues, security concerns
- **Border**: Thin purple left border
- **Icon**: Critical warning symbol

---

## Complete Error Catalog by Component

### 1. File Operations Errors

#### 🔴 **Permission Denied**
- **User Message**: "Cannot access files or destination. Please check permissions and try again."
- **Severity**: ERROR
- **Trigger**: User lacks read/write permissions on source or destination
- **Technical Context**: File paths, operation type, permission details
- **Recoverable**: Yes - User can fix permissions

#### 🔴 **File Not Found**
- **User Message**: "One or more files could not be found. They may have been moved or deleted."
- **Severity**: ERROR
- **Trigger**: Source files missing during copy operation
- **Technical Context**: Missing file paths, operation stage
- **Recoverable**: Yes - User can select different files

#### 🔴 **System Error**
- **User Message**: "A system error occurred. Please check available disk space and try again."
- **Severity**: ERROR
- **Trigger**: OS-level errors (disk full, I/O errors, etc.)
- **Technical Context**: System error codes, disk space info, operation details
- **Recoverable**: Yes - User can resolve system issues

#### 🟣 **Unexpected File Error**
- **User Message**: "An unexpected error occurred during file copying. Please try again."
- **Severity**: CRITICAL
- **Trigger**: Unhandled exceptions during file operations
- **Technical Context**: Exception details, stack trace, operation state
- **Recoverable**: Maybe - Depends on underlying issue

#### 🔴 **Validation Error (Empty Files)**
- **User Message**: "No files selected. Please select files to copy."
- **Severity**: ERROR
- **Trigger**: User attempts operation without selecting files
- **Technical Context**: Expected vs actual file count
- **Recoverable**: Yes - User must select files

#### 🔴 **Validation Error (No Destination)**
- **User Message**: "No destination folder selected. Please choose where to copy files."
- **Severity**: ERROR
- **Trigger**: User attempts operation without destination
- **Technical Context**: Operation type, missing destination path
- **Recoverable**: Yes - User must select destination

### 2. Hash Verification Errors

#### 🟣 **Hash Verification Failure**
- **User Message**: "Hash verification failed. File integrity may be compromised."
- **Severity**: CRITICAL
- **Trigger**: Source and destination file hashes don't match
- **Technical Context**: File paths, expected vs actual hash values, verification algorithm
- **Recoverable**: No - Indicates potential data corruption

#### 🔴 **Hash Calculation Error**
- **User Message**: "Hash calculation failed for some files. File integrity verification incomplete."
- **Severity**: ERROR
- **Trigger**: Unable to calculate hash due to file access issues
- **Technical Context**: Affected files, hash algorithm, error details
- **Recoverable**: Yes - Retry operation or skip hash verification

### 3. Report Generation Errors

#### 🔴 **PDF Permission Error**
- **User Message**: "Cannot create report. Please check folder permissions."
- **Trigger Examples**:
  - Time Offset Report: "Cannot create Time Offset Report. Please check folder permissions."
  - Technician Log: "Cannot create Technician Log. Please check folder permissions."
  - Hash CSV: "Cannot create Hash Verification CSV. Please check folder permissions."
- **Severity**: ERROR
- **Technical Context**: Report type, output path, permission details
- **Recoverable**: Yes - User can fix folder permissions

#### 🟣 **PDF Generation Failure**
- **User Message**: Various by report type:
  - "Time Offset Report generation failed due to an unexpected error."
  - "Technician Log generation failed due to an unexpected error."
  - "Hash Verification CSV generation failed due to an unexpected error."
- **Severity**: CRITICAL
- **Trigger**: Unexpected errors during PDF/CSV creation
- **Technical Context**: Report type, output path, exception details
- **Recoverable**: Maybe - Depends on underlying cause

### 4. Archive (ZIP) Creation Errors

#### 🔴 **Archive Creation Failed**
- **User Message**: "Archive creation failed. Please check available disk space."
- **Severity**: ERROR
- **Trigger**: ZIP creation failures (disk space, permissions, etc.)
- **Technical Context**: Archive path, compression settings, error details
- **Recoverable**: Yes - User can free disk space or change location

#### 🔴 **Archive Permission Error**
- **User Message**: "Cannot create archive. Please check folder permissions."
- **Severity**: ERROR
- **Trigger**: Permission denied when creating ZIP files
- **Technical Context**: Archive path, permission details, operation stage
- **Recoverable**: Yes - User can fix permissions

### 5. Batch Processing Errors

#### 🔵 **Batch Complete (All Success)**
- **User Message**: "Batch job completed successfully (X items processed)"
- **Severity**: INFO
- **Trigger**: All items in batch processed successfully
- **Technical Context**: Job ID, total items processed, processing time
- **Auto-dismiss**: 5 seconds

#### 🟡 **Batch Partial Success**
- **User Message**: "Batch job partially successful: X completed, Y failed"
- **Severity**: WARNING
- **Trigger**: Some items succeeded, some failed
- **Technical Context**: Job ID, success/failure counts, error details for failed items
- **Auto-dismiss**: 8 seconds

#### 🟣 **Batch Complete Failure**
- **User Message**: "Batch job failed completely (X errors)"
- **Severity**: CRITICAL
- **Trigger**: All items in batch failed
- **Technical Context**: Job ID, failure count, detailed error information
- **Recoverable**: Yes - User can address issues and retry

### 6. Form Validation Errors

#### 🟡 **Single Field Error**
- **User Message**: "Please correct the validation error."
- **Severity**: WARNING
- **Trigger**: One form field has invalid data
- **Technical Context**: Field name, validation rule violated, expected format
- **Auto-dismiss**: 8 seconds
- **Recoverable**: Yes - User can correct the field

#### 🟡 **Multiple Field Errors**
- **User Message**: "Please correct X validation errors."
- **Severity**: WARNING
- **Trigger**: Multiple form fields have invalid data
- **Technical Context**: Field names and error messages, validation rules
- **Auto-dismiss**: 8 seconds
- **Recoverable**: Yes - User can correct all fields

### 7. Configuration Errors

#### 🟡 **Configuration Error**
- **User Message**: "Configuration error. Please check application settings."
- **Severity**: WARNING
- **Trigger**: Invalid settings values, missing configuration
- **Technical Context**: Setting key, expected vs actual values, configuration section
- **Auto-dismiss**: 8 seconds
- **Recoverable**: Yes - User can fix settings

#### 🔴 **Settings Load Error**
- **User Message**: "Cannot load application settings. Using defaults."
- **Severity**: ERROR
- **Trigger**: Corrupted settings file, permission issues
- **Technical Context**: Settings file path, error details, default values applied
- **Recoverable**: Partial - Application continues with defaults

### 8. Thread/System Errors

#### 🟣 **Thread Error**
- **User Message**: "Internal processing error. Please restart the operation."
- **Severity**: CRITICAL
- **Trigger**: Thread synchronization issues, worker thread failures
- **Technical Context**: Thread name, error details, operation state
- **Recoverable**: Maybe - Restart operation or application

#### 🔴 **Memory Error**
- **User Message**: "Insufficient memory to complete operation. Please close other applications."
- **Severity**: ERROR
- **Trigger**: Out of memory conditions during large operations
- **Technical Context**: Memory usage, operation size, system resources
- **Recoverable**: Yes - User can free memory

### 9. User Interface Errors

#### 🟡 **UI Component Error**
- **User Message**: "Interface error occurred. Please try the operation again."
- **Severity**: WARNING
- **Trigger**: UI component failures, widget state issues
- **Technical Context**: Component name, error details, user action that triggered error
- **Auto-dismiss**: 8 seconds
- **Recoverable**: Yes - Retry operation

#### 🔴 **Dialog Error**
- **User Message**: "Cannot open dialog. Please restart the application."
- **Severity**: ERROR
- **Trigger**: Dialog creation failures, resource issues
- **Technical Context**: Dialog type, initialization error, resource usage
- **Recoverable**: Maybe - Restart application

---

## Error Context Information

### Technical Details Available (via Details Button)

Each error notification provides detailed technical information accessible through the "Details" button:

#### **Error Identification**
- **Error Code**: Unique identifier (e.g., "FileOperationError", "ValidationError")
- **Timestamp**: When error occurred (UTC format)
- **Thread Information**: Main thread vs worker thread, thread ID
- **Component**: Which part of application generated error

#### **Contextual Data**
- **Operation Details**: What operation was being performed
- **File Paths**: Source and destination paths (when applicable)
- **Parameters**: Operation parameters and settings
- **System Information**: Relevant system state (disk space, permissions, etc.)

#### **Recovery Information**
- **Recoverable Status**: Whether error can be resolved by user action
- **Suggested Actions**: Specific steps to resolve the issue
- **Related Settings**: Configuration options that might affect the error

---

## Common Error Scenarios & Solutions

### File Operations
1. **Permission Denied**
   - **Cause**: User lacks permissions
   - **Solution**: Change file/folder permissions or run as administrator
   - **Prevention**: Check permissions before operations

2. **Disk Space Issues**
   - **Cause**: Insufficient disk space for copy operations
   - **Solution**: Free disk space or choose different destination
   - **Prevention**: Monitor disk space before large operations

3. **File Access Conflicts**
   - **Cause**: Files in use by other applications
   - **Solution**: Close applications using files
   - **Prevention**: Ensure files are not locked before operations

### Report Generation
1. **Output Folder Issues**
   - **Cause**: Cannot write to Documents folder
   - **Solution**: Ensure output folder exists and is writable
   - **Prevention**: Verify output paths before generation

2. **Resource Exhaustion**
   - **Cause**: Large reports exceed memory limits
   - **Solution**: Close other applications, restart if needed
   - **Prevention**: Monitor system resources during large operations

### Hash Verification
1. **Integrity Failures**
   - **Cause**: File corruption during copy
   - **Solution**: Retry operation, check source file integrity
   - **Prevention**: Use reliable storage, verify source files

---

## Migration Impact for Users

### Before Nuclear Migration
- **67 blocking modal dialogs**
- **Inconsistent error messages**
- **No severity indication**
- **Limited context information**
- **Workflow interruption**

### After Nuclear Migration
- **Non-blocking notifications**
- **Consistent, clear messaging**
- **Visual severity indicators**
- **Rich technical context on demand**
- **Continuous workflow**

### User Benefits
1. **Productivity**: No workflow interruption from modal dialogs
2. **Clarity**: Severity-based color coding and consistent messaging
3. **Control**: Manual dismiss for important errors, auto-dismiss for minor issues
4. **Debugging**: Detailed technical information when needed
5. **Context**: Clear understanding of what went wrong and how to fix it

---

## Developer Notes

### Error Emission Pattern
```python
# Standard error handling pattern used throughout codebase
try:
    # Operation
except SpecificException as e:
    error = SpecificFSAError(
        technical_message,
        user_message="User-friendly message",
        severity=ErrorSeverity.LEVEL
    )
    handle_error(error, {'context': 'additional_info'})
    return Result.error(error)
```

### Context Preservation
All errors maintain rich context including:
- Operation being performed
- Component that generated error
- Thread information
- Relevant file paths and parameters
- System state information

### Thread Safety
- All error handling is thread-safe via Qt signal routing
- Worker threads emit errors that are routed to main thread for UI display
- No direct UI manipulation from worker threads

---

## Conclusion

The new error notification system provides users with a comprehensive, non-blocking way to understand and respond to application errors. The system maintains all the necessary technical information for debugging while presenting user-friendly messages and clear recovery guidance.

**Key Improvements:**
- ✅ **No workflow interruption** - Users can continue working
- ✅ **Better error awareness** - Visual severity indicators and consistent placement
- ✅ **Improved usability** - Auto-dismiss for minor issues, persistent for critical ones
- ✅ **Enhanced debugging** - Rich technical context available on demand
- ✅ **Consistent experience** - All errors use same notification system

This represents a significant improvement in user experience while maintaining the technical depth required for forensic evidence processing applications.

---

*This catalog documents all error notifications in the nuclear error handling system as of the complete Phase 4 implementation. Users will see these notifications instead of the previous modal dialogs, providing a modern, non-blocking error handling experience.*
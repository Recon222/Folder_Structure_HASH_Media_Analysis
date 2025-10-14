#!/usr/bin/env python3
"""Test WMI storage detection capabilities"""

import wmi
import sys

def test_wmi_storage_detection():
    """Test WMI-based storage detection for NVMe vs SATA"""

    print("=" * 80)
    print("WMI Storage Detection Test")
    print("=" * 80)

    try:
        # Try storage namespace first (Windows 8+)
        try:
            c = wmi.WMI(namespace=r"root\microsoft\windows\storage")
            print("\n[OK] Connected to WMI Storage namespace")
            use_storage_namespace = True
        except Exception as e1:
            print(f"\n[SKIP] Storage namespace not available: {e1}")
            print("[INFO] Falling back to standard WMI")
            c = wmi.WMI()
            use_storage_namespace = False

        # BusType enum values (from Microsoft docs)
        bus_types = {
            0: "Unknown",
            1: "SCSI",
            2: "ATAPI",
            3: "ATA",
            4: "1394",
            5: "SSA",
            6: "Fibre Channel",
            7: "USB",
            8: "RAID",
            9: "iSCSI",
            10: "SAS",
            11: "SATA",
            12: "SD",
            13: "MMC",
            14: "Virtual",
            15: "File Backed Virtual",
            16: "Storage Spaces",
            17: "NVMe",
            18: "Microsoft Reserved"
        }

        media_types = {
            0: "Unspecified",
            3: "HDD",
            4: "SSD",
            5: "SCM"
        }

        if use_storage_namespace:
            # Test MSFT_PhysicalDisk
            print("\n" + "=" * 80)
            print("MSFT_PhysicalDisk - Physical Drive Information")
            print("=" * 80)

            physical_disks = list(c.MSFT_PhysicalDisk())
            print(f"\nFound {len(physical_disks)} physical disk(s)")

            for disk in physical_disks:
                print(f"\n  Physical Disk #{disk.DeviceId}")
                print(f"    FriendlyName: {disk.FriendlyName}")
                print(f"    Model: {disk.Model}")

                bus_type_num = disk.BusType
                bus_type_name = bus_types.get(bus_type_num, f"Unknown ({bus_type_num})")
                print(f"    BusType: {bus_type_num} = {bus_type_name}")

                media_type_num = disk.MediaType
                media_type_name = media_types.get(media_type_num, f"Unknown ({media_type_num})")
                print(f"    MediaType: {media_type_num} = {media_type_name}")

                try:
                    size_gb = int(disk.Size) / (1024**3)
                    print(f"    Size: {size_gb:.2f} GB")
                except:
                    print(f"    Size: {disk.Size}")

                # Determine what our detection would say
                if bus_type_num == 17:
                    detected = "NVMe (via BusType=17)"
                elif bus_type_num == 11:
                    detected = "SATA SSD (via BusType=11)"
                elif media_type_num == 3:
                    detected = "HDD (via MediaType=3)"
                else:
                    detected = f"Unknown - would fall back to performance test"
                print(f"    -> Detection: {detected}")

            # Build drive letter mapping
            print("\n" + "=" * 80)
            print("Drive Letter -> Bus Type Mapping")
            print("=" * 80)

            logical_disks = list(c.MSFT_Disk())
            print(f"\nFound {len(logical_disks)} logical disk(s)")

            drive_map = {}
            for disk in logical_disks:
                try:
                    partitions = disk.associators(wmi_result_class="MSFT_Partition")
                    for partition in partitions:
                        volumes = partition.associators(wmi_result_class="MSFT_Volume")
                        for volume in volumes:
                            if volume.DriveLetter:
                                bus_type_num = disk.BusType
                                bus_type_name = bus_types.get(bus_type_num, f"Unknown ({bus_type_num})")
                                drive_map[volume.DriveLetter] = (bus_type_num, bus_type_name, disk.FriendlyName)
                except:
                    pass

            for drive_letter in sorted(drive_map.keys()):
                bus_num, bus_name, friendly = drive_map[drive_letter]
                print(f"\n  {drive_letter}: -> BusType {bus_num} ({bus_name})")
                print(f"      Disk: {friendly}")

                if bus_num == 17:
                    print(f"      [OK] Would detect as NVMe")
                elif bus_num == 11:
                    print(f"      [OK] Would detect as SATA SSD")
                else:
                    print(f"      [WARN] Would fall back to performance test")

            print("\n" + "=" * 80)
            print("Summary")
            print("=" * 80)
            print(f"\n[OK] WMI detection is AVAILABLE")
            print(f"[OK] Found {len(physical_disks)} physical disk(s)")
            print(f"[OK] Found {len(drive_map)} drive letter(s) with bus type info")
            print(f"\nRecommendation: Add WMI as Tier 0 detection (before performance tests)")
            print(f"  - Fast (no disk I/O)")
            print(f"  - Reliable (OS-provided)")
            print(f"  - Fall back to performance tests only if BusType=Unknown")

        else:
            # Fallback to Win32_DiskDrive (limited info)
            print("\n" + "=" * 80)
            print("Win32_DiskDrive - Physical Drive Information (Legacy WMI)")
            print("=" * 80)

            physical_disks = list(c.Win32_DiskDrive())
            print(f"\nFound {len(physical_disks)} physical disk(s)")

            for i, disk in enumerate(physical_disks):
                print(f"\n  Disk #{i}")
                print(f"    Caption: {disk.Caption}")
                print(f"    Model: {disk.Model}")
                print(f"    InterfaceType: {disk.InterfaceType}")
                print(f"    Size: {int(disk.Size) / (1024**3):.2f} GB")

            print("\n[WARN] Win32_DiskDrive has no BusType property")
            print("[INFO] Must use performance test fallback for all drives")

    except Exception as e:
        print(f"\n[FAIL] Error accessing WMI: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_wmi_storage_detection()

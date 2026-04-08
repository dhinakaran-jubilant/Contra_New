from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
import os
import uuid
import base64
from pathlib import Path
from .consolidate import merge_excel_files
from api import helpers

class ConsolidateView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        action = request.data.get("action", "merge")
        
        try:
            if action == "merge":
                excel_files = request.FILES.getlist("files")
                if not excel_files:
                    return Response({"error": "No files uploaded."}, status=status.HTTP_400_BAD_REQUEST)

                # 1. Create a unique temporary directory
                temp_id = str(uuid.uuid4())
                temp_dir = Path("temp_consolidate") / temp_id
                temp_dir.mkdir(parents=True, exist_ok=True)

                file_paths = []
                # 2. Save uploaded files
                for f in excel_files:
                    file_path = temp_dir / f.name
                    with open(file_path, 'wb+') as destination:
                        for chunk in f.chunks():
                            destination.write(chunk)
                    file_paths.append(str(file_path.absolute()))

                # 3. Perform validation and merge
                from .consolidate import validate_excel_files, merge_excel_files
                
                is_valid, err_msg, pivot_count, xns_count = validate_excel_files(file_paths)
                if not is_valid:
                    return Response({"error": err_msg}, status=status.HTTP_400_BAD_REQUEST)

                skip_cons = False
                if len(file_paths) == 1:
                    # Single file bypass: skip merge logic
                    consolidated_path = file_paths[0]
                    # Skip CONS only if it's a "simple" single file (1 pivot, 1 xns)
                    # If it has 2+ of each, we still want the summary.
                    if pivot_count < 2 or xns_count < 2:
                        skip_cons = True
                else:
                    consolidated_path = merge_excel_files(file_paths)
                
                if not consolidated_path or not os.path.exists(consolidated_path):
                    return Response({"error": "Merge failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Clean up individual uploads only if we actually merged
                if not skip_cons:
                    for p in file_paths:
                        if p != consolidated_path and os.path.exists(p):
                            try: os.remove(p)
                            except: pass

                return Response({
                    "success": True,
                    "action": "merge",
                    "file_path": consolidated_path,
                    "skip_cons": skip_cons,
                    "message": "File(s) processed successfully."
                })

            elif action == "cons":
                file_path = request.data.get("file_path")
                if not file_path or not os.path.exists(file_path):
                    return Response({"error": "File path missing or invalid."}, status=status.HTTP_400_BAD_REQUEST)

                from .cons import create_cons_sheet
                create_cons_sheet(file_path)
                
                return Response({
                    "success": True,
                    "action": "cons",
                    "file_path": file_path,
                    "message": "Summary sheet created."
                })

            elif action == "charts":
                file_path = request.data.get("file_path")
                if not file_path or not os.path.exists(file_path):
                    return Response({"error": "File path missing or invalid."}, status=status.HTTP_400_BAD_REQUEST)

                from .chart import create_chart_from_pivot
                create_chart_from_pivot(file_path)

                # Prepare final download URL
                encoded_path = base64.b64encode(str(file_path).encode()).decode()
                download_url = f"/api/download-file/?file_path={encoded_path}"
                
                base_name = os.path.basename(file_path)
                import re
                if not re.search(r'-CONSOLIDATED', base_name, re.IGNORECASE):
                    name_part, ext_part = os.path.splitext(base_name)
                    final_name = f"{name_part}-CONSOLIDATED{ext_part}"
                else:
                    final_name = base_name

                # Update Google Sheets with 'Final' stats
                try:
                    from api.update_sheet import update_google_sheets_final
                    print(f"📊 Triggering final Google Sheets update for: {file_path}")
                    update_google_sheets_final(file_path)
                except Exception as gs_err:
                    print(f"⚠️ Google Sheets final update failed: {gs_err}")

                # Log processing details for database: Update existing logs from Contra Match with Final Counts
                try:
                    import pandas as pd
                    from api.helpers import log_processing, format_category_counts, update_processing_log_final
                    xl = pd.ExcelFile(file_path)
                    consolidated_details = []
                    total_entries = 0
                    
                    # 1. Iterate through sheets to find XNS data
                    for sn in xl.sheet_names:
                        if "XNS" in sn.upper():
                            df = pd.read_excel(xl, sheet_name=sn)
                            
                            # Get formatted transaction counts for this sheet
                            counts_str = format_category_counts(df)
                            
                            # Update existing log entry (matching sheet name as substring of filename)
                            # Sheet name is usually 'ACC-BANK' or 'BANK-ACC'
                            update_processing_log_final(sn, counts_str)
                            
                            consolidated_details.append(f"{str(sn).replace(' ', '_').lower()}: {len(df)}")
                            total_entries += len(df)
                    
                    # 2. Removed redundant "CONSOLIDATED" log entry as requested.
                    # We only update existing matched rows.
                except Exception as log_err:
                    print(f"⚠️ Consolidation logging update failed: {log_err}")

                return Response({
                    "success": True,
                    "action": "charts",
                    "download_files": [
                        {
                            "file_name": final_name,
                            "download_url": download_url
                        }
                    ],
                    "message": "Charts generated and file ready."
                })

            else:
                return Response({"error": f"Unknown action: {action}"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

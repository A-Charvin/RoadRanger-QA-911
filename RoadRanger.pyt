import arcpy
import os


class Toolbox:
    def __init__(self):
        self.label = "RoadRanger"
        self.alias = "RoadRanger"
        self.tools = [ValidateRoadRanges]


class ValidateRoadRanges:
    def __init__(self):
        self.label = "RoadRanger"
        self.description = (
            "Validates road segment address ranges for NG911:\n"
            "- Individual range checks (reversed, null, parity)\n"
            "- Cross-segment continuity (gaps, overlaps, side switches)\n"
            "Outputs segments with detected issues."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        p_road = arcpy.Parameter(
            displayName="Road Segment Layer",
            name="road_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        p_road_name = arcpy.Parameter(
            displayName="Road - Street Name Field",
            name="road_name_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_road_name.parameterDependencies = ["road_fc"]
        p_road_name.filter.list = ["Text"]

        p_fL = arcpy.Parameter(
            displayName="Road - From Address Left Field",
            name="road_fL_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_fL.parameterDependencies = ["road_fc"]

        p_tL = arcpy.Parameter(
            displayName="Road - To Address Left Field",
            name="road_tL_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_tL.parameterDependencies = ["road_fc"]

        p_fR = arcpy.Parameter(
            displayName="Road - From Address Right Field",
            name="road_fR_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_fR.parameterDependencies = ["road_fc"]

        p_tR = arcpy.Parameter(
            displayName="Road - To Address Right Field",
            name="road_tR_field",
            datatype="Field",
            parameterType="Required",
            direction="Input"
        )
        p_tR.parameterDependencies = ["road_fc"]

        p_out_gdb = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="out_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )
        p_out_gdb.filter.list = ["Local Database"]
        p_out_gdb.defaultEnvironmentName = "workspace"

        p_out_name = arcpy.Parameter(
            displayName="Output Feature Class Name",
            name="out_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p_out_name.value = "Road_Validation_Issues"

        p_tolerance = arcpy.Parameter(
            displayName="Segment Connection Tolerance (meters)",
            name="tolerance",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input"
        )
        p_tolerance.value = 10

        return [p_road, p_road_name, p_fL, p_tL, p_fR, p_tR,
                p_out_gdb, p_out_name, p_tolerance]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        if parameters[0].altered and not parameters[0].hasError():
            desc = arcpy.Describe(parameters[0].valueAsText)
            if desc.shapeType != "Polyline":
                parameters[0].setErrorMessage(
                    "Road layer must be a Polyline feature class.")
        return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def safe_float(value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if value == '':
                return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def get_parity(num):
        if num is None:
            return None
        try:
            return 'EVEN' if int(num) % 2 == 0 else 'ODD'
        except Exception:
            return None

    @staticmethod
    def get_normalized_range(from_addr, to_addr):
        """Return (low, high, parity). Parity is MIXED if low/high differ."""
        from_val = ValidateRoadRanges.safe_float(from_addr)
        to_val   = ValidateRoadRanges.safe_float(to_addr)
        if from_val is None or to_val is None:
            return None, None, None
        low  = min(from_val, to_val)
        high = max(from_val, to_val)
        p_low  = ValidateRoadRanges.get_parity(low)
        p_high = ValidateRoadRanges.get_parity(high)
        parity = p_low if p_low == p_high else 'MIXED'
        return low, high, parity

    @staticmethod
    def format_value(val):
        if val is None:
            return "NULL"
        try:
            return str(int(val))
        except Exception:
            return str(val)

    @staticmethod
    def truncate_text(text, max_length=247):
        if not text or len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    @staticmethod
    def get_segment_endpoints(geometry):
        if geometry is None or geometry.partCount == 0:
            return None, None
        part   = geometry.getPart(0)
        points = [pt for pt in part if pt]
        if len(points) >= 2:
            return (points[0].X, points[0].Y), (points[-1].X, points[-1].Y)
        return None, None

    @staticmethod
    def calculate_distance(p1, p2):
        if p1 is None or p2 is None:
            return None
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    # ------------------------------------------------------------------
    # Individual segment validation
    # Catches data-entry errors on a single segment only.
    # Range SIZE is intentionally not validated — segments vary in length.
    # ------------------------------------------------------------------
    def validate_single_segment(self, oid, fL, tL, fR, tR):
        issues = []

        L_low, L_high, L_parity = self.get_normalized_range(fL, tL)
        R_low, R_high, R_parity = self.get_normalized_range(fR, tR)

        # Null / unparseable values
        if L_low is None:
            issues.append("Left range missing/invalid")
        if R_low is None:
            issues.append("Right range missing/invalid")
        if L_low is None or R_low is None:
            return issues

        # Reversed direction (from > to)
        fL_f = self.safe_float(fL)
        tL_f = self.safe_float(tL)
        fR_f = self.safe_float(fR)
        tR_f = self.safe_float(tR)
        if fL_f is not None and tL_f is not None and fL_f > tL_f:
            issues.append(
                f"Left range reversed ({self.format_value(fL)}->{self.format_value(tL)})")
        if fR_f is not None and tR_f is not None and fR_f > tR_f:
            issues.append(
                f"Right range reversed ({self.format_value(fR)}->{self.format_value(tR)})")

        # Single-number range (from == to)
        if L_low == L_high:
            issues.append(f"Left range is a single number ({int(L_low)})")
        if R_low == R_high:
            issues.append(f"Right range is a single number ({int(R_low)})")

        # Mixed parity within one side (e.g. 101-200 spans odd and even)
        if L_parity == 'MIXED':
            issues.append(
                f"Left range mixed parity ({int(L_low)}-{int(L_high)})")
        if R_parity == 'MIXED':
            issues.append(
                f"Right range mixed parity ({int(R_low)}-{int(R_high)})")

        # Both sides same parity (left and right should be opposite)
        if (L_parity not in (None, 'MIXED') and R_parity not in (None, 'MIXED')
                and L_parity == R_parity):
            issues.append(
                f"Both sides {L_parity} parity (expected opposite sides)")

        # Start numbers not consecutive (e.g. L=101, R=104 — 102/103 skipped)
        if abs(L_low - R_low) != 1:
            issues.append(
                f"Start numbers not consecutive "
                f"(L:{int(L_low)}, R:{int(R_low)}, diff:{int(abs(L_low - R_low))})")

        # End numbers not consecutive
        if abs(L_high - R_high) != 1:
            issues.append(
                f"End numbers not consecutive "
                f"(L:{int(L_high)}, R:{int(R_high)}, diff:{int(abs(L_high - R_high))})")

        # NOTE: Span size (number of addresses covered) is NOT validated.
        # Segments are split at intersections and vary freely in size.

        return issues

    # ------------------------------------------------------------------
    # Cross-segment continuity validation
    #
    # The address sequence must be unbroken across connected segments:
    #
    #   seg1: ...98(L), 99(R), 100(L), 101(R)   <- ends at max=101
    #   seg2: 102(L), 103(R)...                  <- starts at min=102
    #   diff = 102 - 101 = 1  -> correct
    #
    # diff > 1  -> gap   (addresses missing between segments)
    # diff < 1  -> overlap (addresses duplicated / segment order wrong)
    # diff == 1 -> correct
    # ------------------------------------------------------------------
    def validate_segment_pair(self, seg1, seg2):
        issues = []

        oid1, name1, fL1, tL1, fR1, tR1, first1, last1, shp1 = seg1
        oid2, name2, fL2, tL2, fR2, tR2, first2, last2, shp2 = seg2

        L1_low, L1_high, L1_parity = self.get_normalized_range(fL1, tL1)
        R1_low, R1_high, R1_parity = self.get_normalized_range(fR1, tR1)
        L2_low, L2_high, L2_parity = self.get_normalized_range(fL2, tL2)
        R2_low, R2_high, R2_parity = self.get_normalized_range(fR2, tR2)

        if None in [L1_low, L1_high, R1_low, R1_high,
                    L2_low, L2_high, R2_low, R2_high]:
            return issues

        # ---- Parity consistency across the boundary -------------------
        if L1_parity not in (None, 'MIXED') and L2_parity not in (None, 'MIXED'):
            if L1_parity != L2_parity:
                issues.append(
                    f"Left parity changes at boundary: "
                    f"{L1_parity} (OID {oid1}) -> {L2_parity} (OID {oid2})")

        if R1_parity not in (None, 'MIXED') and R2_parity not in (None, 'MIXED'):
            if R1_parity != R2_parity:
                issues.append(
                    f"Right parity changes at boundary: "
                    f"{R1_parity} (OID {oid1}) -> {R2_parity} (OID {oid2})")

        # ---- Side switch (L/R flipped between segments) ---------------
        if (L1_parity not in (None, 'MIXED') and R1_parity not in (None, 'MIXED') and
                L2_parity not in (None, 'MIXED') and R2_parity not in (None, 'MIXED')):
            if L1_parity != R1_parity:  # seg1 is internally valid
                if L1_parity == R2_parity and R1_parity == L2_parity:
                    issues.append(
                        f"SIDE SWITCH: L/R swapped between OID {oid1} "
                        f"(L={L1_parity}/R={R1_parity}) and OID {oid2} "
                        f"(L={L2_parity}/R={R2_parity})")

        # ---- Gap / overlap in the number sequence ---------------------
        max_seg1 = max(L1_high, R1_high)
        min_seg2 = min(L2_low,  R2_low)
        diff     = min_seg2 - max_seg1

        if diff > 1:
            # One or more addresses are missing at the boundary
            missing_start = int(max_seg1) + 1
            missing_end   = int(min_seg2) - 1
            if missing_start == missing_end:
                missing_str = str(missing_start)
            else:
                missing_str = f"{missing_start}-{missing_end}"
            issues.append(
                f"GAP: address(es) {missing_str} missing between "
                f"OID {oid1} (ends {int(max_seg1)}) and "
                f"OID {oid2} (starts {int(min_seg2)})")

        elif diff < 1:
            # Addresses duplicated or segments are in the wrong order
            issues.append(
                f"OVERLAP: OID {oid1} ends {int(max_seg1)}, "
                f"OID {oid2} starts {int(min_seg2)} "
                f"(overlap of {int(1 - diff)} address(es))")

        return issues

    # ------------------------------------------------------------------
    # Chain segments along a street by endpoint proximity
    # ------------------------------------------------------------------
    @staticmethod
    def chain_segments(segments, tolerance):
        """
        Greedy nearest-neighbour chain along a street.
        Disconnected segments are still appended so they receive
        individual QA; cross-segment checks are skipped for
        disconnected pairs in execute().
        """
        remaining = list(segments)
        chain     = [remaining.pop(0)]

        while remaining:
            current_last = chain[-1][7]
            best_dist    = float('inf')
            best_idx     = -1

            for i, seg in enumerate(remaining):
                d = ValidateRoadRanges.calculate_distance(current_last, seg[6])
                if d is not None and d < best_dist:
                    best_dist = d
                    best_idx  = i

            if best_idx >= 0 and best_dist <= tolerance:
                chain.append(remaining.pop(best_idx))
            else:
                chain.append(remaining.pop(0))

        return chain

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------
    def execute(self, parameters, messages):
        road_fc   = parameters[0].valueAsText
        name_fld  = parameters[1].valueAsText
        fL_fld    = parameters[2].valueAsText
        tL_fld    = parameters[3].valueAsText
        fR_fld    = parameters[4].valueAsText
        tR_fld    = parameters[5].valueAsText
        out_gdb   = parameters[6].valueAsText
        out_name  = parameters[7].valueAsText
        tolerance = float(parameters[8].value)

        output_fc = os.path.join(out_gdb, out_name)
        sr        = arcpy.Describe(road_fc).spatialReference

        messages.addMessage("=" * 60)
        messages.addMessage("ROADRANGER NG911 - ROAD ADDRESS VALIDATION")
        messages.addMessage("=" * 60)
        messages.addMessage(f"Connection tolerance: {tolerance} meters")
        messages.addMessage("=" * 60)

        # ------------------------------------------------------------------
        # Read segments
        # ------------------------------------------------------------------
        messages.addMessage("Reading road segments...")

        # "OID@" is an ArcPy token that resolves to the correct OID field
        road_fields   = ["OID@", name_fld, fL_fld, tL_fld,
                         fR_fld, tR_fld, "SHAPE@"]
        streets       = {}   # street_key -> [segment tuples]
        segment_data  = {}   # oid -> attribute dict
        issues_by_oid = {}   # oid -> [issue strings]

        with arcpy.da.SearchCursor(road_fc, road_fields) as cur:
            for row in cur:
                oid   = row[0]
                name  = row[1] if row[1] else "UNNAMED"
                fL, tL, fR, tR = row[2], row[3], row[4], row[5]
                shape = row[6]

                street_key        = name.upper().strip()
                first_pt, last_pt = self.get_segment_endpoints(shape)

                segment_data[oid] = {
                    'name': name, 'fL': fL, 'tL': tL,
                    'fR': fR, 'tR': tR, 'shape': shape
                }

                seg_issues = self.validate_single_segment(oid, fL, tL, fR, tR)
                if seg_issues:
                    issues_by_oid[oid] = seg_issues

                streets.setdefault(street_key, []).append(
                    (oid, name, fL, tL, fR, tR, first_pt, last_pt, shape)
                )

        total_segments = sum(len(v) for v in streets.values())
        messages.addMessage(
            f"Read {total_segments} segments across {len(streets)} streets.")

        # ------------------------------------------------------------------
        # Cross-segment continuity
        # ------------------------------------------------------------------
        messages.addMessage("Checking segment continuity...")
        continuity_issues_found = 0

        for street_name, segments in streets.items():
            if len(segments) < 2:
                continue

            ordered = self.chain_segments(segments, tolerance)

            for i in range(len(ordered) - 1):
                seg1 = ordered[i]
                seg2 = ordered[i + 1]

                # Only check pairs that are actually spatially connected
                dist = self.calculate_distance(seg1[7], seg2[6])
                if dist is None or dist > tolerance:
                    continue

                pair_issues = self.validate_segment_pair(seg1, seg2)
                if not pair_issues:
                    continue

                continuity_issues_found += len(pair_issues)
                oid2 = seg2[0]
                if oid2 in issues_by_oid:
                    issues_by_oid[oid2].extend(pair_issues)
                else:
                    issues_by_oid[oid2] = list(pair_issues)

        messages.addMessage(
            f"Found {continuity_issues_found} continuity issues.")

        # ------------------------------------------------------------------
        # Create output feature class
        # ------------------------------------------------------------------
        messages.addMessage(f"Creating output: {out_name}")

        if arcpy.Exists(output_fc):
            arcpy.Delete_management(output_fc)

        arcpy.CreateFeatureclass_management(
            out_path=out_gdb,
            out_name=out_name,
            geometry_type="POLYLINE",
            spatial_reference=sr
        )

        arcpy.AddField_management(output_fc, "RoadOID",    "LONG")
        arcpy.AddField_management(output_fc, "StreetName", "TEXT", field_length=100)
        arcpy.AddField_management(output_fc, "IssueCount", "SHORT")
        arcpy.AddField_management(output_fc, "Issues",     "TEXT", field_length=250)
        arcpy.AddField_management(output_fc, "FromLeft",   "TEXT", field_length=20)
        arcpy.AddField_management(output_fc, "ToLeft",     "TEXT", field_length=20)
        arcpy.AddField_management(output_fc, "FromRight",  "TEXT", field_length=20)
        arcpy.AddField_management(output_fc, "ToRight",    "TEXT", field_length=20)

        insert_fields = [
            "SHAPE@", "RoadOID", "StreetName", "IssueCount", "Issues",
            "FromLeft", "ToLeft", "FromRight", "ToRight"
        ]

        with arcpy.da.InsertCursor(output_fc, insert_fields) as cur:
            for oid, issue_list in issues_by_oid.items():
                if oid not in segment_data:
                    continue
                d = segment_data[oid]
                issues_text = self.truncate_text("; ".join(issue_list), 247)
                cur.insertRow([
                    d['shape'], oid,
                    d['name'] or "UNNAMED",
                    len(issue_list),
                    issues_text,
                    self.format_value(d['fL']),
                    self.format_value(d['tL']),
                    self.format_value(d['fR']),
                    self.format_value(d['tR'])
                ])

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        messages.addMessage("=" * 60)
        messages.addMessage("VALIDATION COMPLETE")
        messages.addMessage("=" * 60)
        messages.addMessage(f"Total segments checked: {total_segments}")
        messages.addMessage(f"Segments with issues:   {len(issues_by_oid)}")
        messages.addMessage(f"Output:                 {output_fc}")

        categories = {
            'missing':         0,
            'reversed':        0,
            'single_number':   0,
            'mixed_parity':    0,
            'same_parity':     0,
            'not_consecutive': 0,
            'parity_change':   0,
            'side_switch':     0,
            'gap':             0,
            'overlap':         0,
            'other':           0,
        }

        for issue_list in issues_by_oid.values():
            for issue in issue_list:
                il = issue.lower()
                if 'missing' in il or 'invalid' in il:
                    categories['missing'] += 1
                elif 'reversed' in il:
                    categories['reversed'] += 1
                elif 'single number' in il:
                    categories['single_number'] += 1
                elif 'mixed parity' in il:
                    categories['mixed_parity'] += 1
                elif 'both sides' in il:
                    categories['same_parity'] += 1
                elif 'not consecutive' in il:
                    categories['not_consecutive'] += 1
                elif 'parity changes' in il:
                    categories['parity_change'] += 1
                elif 'side switch' in il:
                    categories['side_switch'] += 1
                elif 'gap' in il:
                    categories['gap'] += 1
                elif 'overlap' in il:
                    categories['overlap'] += 1
                else:
                    categories['other'] += 1

        messages.addMessage("-" * 40)
        messages.addMessage("ISSUE BREAKDOWN:")
        for cat, count in categories.items():
            if count > 0:
                messages.addMessage(
                    f"  {cat.replace('_', ' ').title()}: {count}")
        messages.addMessage("=" * 60)

        # Add to map
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            if aprx.activeMap:
                aprx.activeMap.addDataFromPath(output_fc)
                messages.addMessage("Output added to active map.")
        except Exception:
            messages.addWarningMessage(
                "Could not add layer to map. Add manually.")

        return

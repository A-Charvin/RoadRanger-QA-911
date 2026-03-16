# RoadRanger QA 911

An ArcGIS Pro Python Toolbox for validating road segment address ranges. RoadRanger catches data-entry errors and continuity breaks in address range data before they cause problems in emergency dispatch.

---

## What it checks

### Per-segment (data entry errors)
| Check | Example flagged |
|---|---|
| Null / unparseable values | Left from address is empty |
| Reversed range | From=900, To=100 |
| Single-number range | From=500, To=500 |
| Mixed parity within a side | Left range 101–200 (spans odd and even) |
| Both sides same parity | Left=ODD, Right=ODD (should be opposite) |
| Non-consecutive start numbers | Left starts 101, Right starts 104 |
| Non-consecutive end numbers | Left ends 199, Right ends 202 |

### Between connected segments (continuity errors)
| Check | Example flagged |
|---|---|
| Gap in address sequence | Seg1 ends 100, Seg2 starts 103 - addresses 101–102 missing |
| Overlap in address sequence | Seg1 ends 100, Seg2 starts 99 - addresses duplicated |
| Parity change across boundary | Left side was ODD, becomes EVEN on next segment |
| Side switch | Left/Right parity flips between connected segments |

---

## Requirements

- ArcGIS Pro 2.x or 3.x
- Python 3.x (bundled with ArcGIS Pro - no additional packages required)
- A Polyline road feature class with address range fields (From Left, To Left, From Right, To Right)

---

## Installation

1. Clone or download this repository.
2. In ArcGIS Pro, open the **CatalogPane**.
3. Navigate to the folder containing `RoadRanger.pyt`.
4. Expand the toolbox - the **RoadRanger** tool will appear inside.

No pip installs or environment setup required.

---

## Usage

1. Open the **RoadRanger** tool.
2. Fill in the parameters:

| Parameter | Description |
|---|---|
| Road Segment Layer | Input polyline feature layer |
| Street Name Field | Text field containing the road name |
| From Address Left | Left side from-address field |
| To Address Left | Left side to-address field |
| From Address Right | Right side from-address field |
| To Address Right | Right side to-address field |
| Output Geodatabase | File geodatabase for results |
| Output Feature Class Name | Name for the output layer (default: `Road_Validation_Issues`) |
| Segment Connection Tolerance | Distance in meters to consider two segment endpoints connected (default: 10m) |

3. Run the tool. The output feature class is added to the active map automatically.

---

## Output

The output is a polyline feature class matching the geometry of flagged road segments, with the following fields:

| Field | Description |
|---|---|
| `RoadOID` | Original OBJECTID of the flagged segment |
| `StreetName` | Street name |
| `IssueCount` | Number of issues found on this segment |
| `Issues` | Semicolon-separated list of issue descriptions |
| `FromLeft` | From address, left side |
| `ToLeft` | To address, left side |
| `FromRight` | From address, right side |
| `ToRight` | To address, right side |

A summary breakdown by issue category is printed to the tool messages on completion.

---

## How continuity checking works

Segments sharing the same street name are spatially chained by endpoint proximity (nearest-neighbour, within the connection tolerance). Adjacent connected pairs are then checked for gaps and overlaps in their address sequence.

The key rule: the highest address number on segment N and the lowest address number on segment N+1 must differ by exactly 1. Anything else is flagged.

Segment size (number of addresses covered) is **not** validated - roads are split at intersections and segment spans vary freely by design.

---

## Example issue messages

```
GAP: address(es) 101 missing between OID 2096 (ends 100) and OID 3408 (starts 102)
OVERLAP: OID 412 ends 200, OID 413 starts 198 (overlap of 3 address(es))
SIDE SWITCH: L/R swapped between OID 88 (L=ODD/R=EVEN) and OID 89 (L=EVEN/R=ODD)
Left range reversed (900->100)
Both sides ODD parity (expected opposite sides)
```

---

## Limitations

- Continuity checking uses a greedy nearest-neighbour chain. Complex intersections or cul-de-sacs may result in a small number of false positives at disconnected segment boundaries - these are skipped automatically when endpoints are beyond the connection tolerance.
- The tool validates address range attributes only. It does not validate geometry, connectivity topology, or against a separate address point layer.

---

## License

MIT License - see [LICENSE](LICENSE).

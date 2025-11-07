# Land Registry

Generates an interactive map and a wiki table for a specific page in the CivWiki. Hardcoded for CivMC

## How to setup

In the land_registry folder:
1. Create a folder named after the wiki page
2. Create a json file with the data (data schema detailed below)
3. Upload a picture export from xaero's minimap (or any other picture, as long as the name format follows xaero's)
4. Run the script

## Land Registry JSON Schema

| Field     | Type                | Required | Description                                                     |
| --------- | ------------------- | -------- | --------------------------------------------------------------- |
| `shape`   | string or object    | ✅        | Plot shape (see below).                                         |
| `owner`   | string              | ✅        | Owner name or group.                                            |
| `date`    | string (YYYY-MM-DD) | ✅        | Registration date.                                              |
| `type`    | string              | ✅        | Zone type: `Residential`, `Commercial`, `Industrial`, `Public`. |
| `name`    | string              | ❌        | Plot or building name.                                          |
| `address` | string              | ❌        | Address or location.                                            |
| `details` | string              | ❌        | Extra description or notes.                                     |

| Shape     | String Example                    | Object Example                                                               |
| --------- | --------------------------------- | ---------------------------------------------------------------------------- |
| Rectangle | `"8097 3854 8108 3842"`           | `{ "p1": {"x":8097,"z":3854}, "p2": {"x":8108,"z":3842} }`                   |
| Circle    | `"8120 3870 5"`                   | `{ "center": {"x":8120,"z":3870}, "radius":5 }`                              |
| Polygon   | `"8097 3854 8108 3842 8110 3860"` | `{ "points":[{"x":8097,"z":3854},{"x":8108,"z":3842},{"x":8110,"z":3860}] }` |

### Example

```json
[
  {
    "shape": "8097 3854 8108 3842",
    "owner": "Passencore",
    "date": "2025-11-06",
    "type": "Commercial",
    "name": "Passen Corner",
    "details": "Café/Brewery",
    "address": "Douro Square, Portucale, Lusitania"
  },
  {
    "shape": { "center": {"x":8120,"z":3870}, "radius":5 },
    "owner": "Portucale",
    "date": "2025-11-06",
    "type": "Public",
    "name": "Town Fountain"
  }
]
```

## Image Name Format

The name format must match this regex: _x(-?\d+)_z(-?\d+)\.png$" where x and z are the bottom left most corner.
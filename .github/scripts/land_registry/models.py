import plotly.graph_objects as go
from abc import ABC, abstractmethod
from pydantic import BaseModel, field_validator
from enum import Enum
from datetime import datetime
from re import search
from math import pi
from os.path import basename, dirname, join
from typing import Callable, Any
from pytablewriter import MediaWikiTableWriter


class ZoneType(str, Enum):
    RESIDENTIAL = "Residential"
    COMMERCIAL = "Commercial"
    INDUSTRIAL = "Industrial"
    PUBLIC = "Public"

    def color(self) -> str:
        match self:
            case ZoneType.RESIDENTIAL:
                return "#4CAF50"  # green
            case ZoneType.COMMERCIAL:
                return "#42A5F5"  # blue
            case ZoneType.INDUSTRIAL:
                return "#FFCA28"  # yellow
            case ZoneType.PUBLIC:
                return "#9E9E9E"
            case _:
                return "#000000"


class Point(BaseModel):
    x: int
    z: int

    def get_plain_string(self, offset_x: int, offset_y: int) -> str:
        return f"{abs(offset_x - self.x)} {abs(offset_y - self.z)}"


class Shape(BaseModel, ABC):
    @abstractmethod
    def get_wiki_imagemap_str(self, offset_x: int, offset_y: int) -> str:
        pass

    @abstractmethod
    def area(self) -> float:
        pass


class Rect(Shape):
    p1: Point
    p2: Point

    def get_wiki_imagemap_str(self, offset_x: int, offset_y: int) -> str:
        return f"rect {self.p1.get_plain_string(offset_x, offset_y)} {self.p2.get_plain_string(offset_x, offset_y)}"

    def area(self) -> float:
        width = abs(self.p2.x - self.p1.x)
        height = abs(self.p2.z - self.p1.z)
        return width * height


class Circle(Shape):
    center: Point
    radius: int

    def get_wiki_imagemap_str(self, offset_x: int, offset_y: int) -> str:
        return (
            f"circle {self.center.get_plain_string(offset_x, offset_y)} {self.radius}"
        )

    def area(self) -> float:
        return pi * (self.radius**2)


class Polygon(Shape):
    points: list[Point]

    def get_wiki_imagemap_str(self, offset_x: int, offset_y: int) -> str:
        return f"poly {' '.join(point.get_plain_string(offset_x, offset_y) for point in self.points)}"

    def area(self) -> float:
        """
        Uses the Shoelace formula (Gauss’s area formula) for polygons.
        """
        n = len(self.points)
        if n < 3:
            return 0.0  # not a polygon
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += self.points[i].x * self.points[j].z
            area -= self.points[j].x * self.points[i].z
        return abs(area) / 2.0


class LandRegistryFile(BaseModel):
    path: str
    data_file: str
    image_file: str
    offset_x: int
    offset_y: int

    def registry_name(self) -> str:
        return basename(dirname(self.data_file))

    def image_map_name(self) -> str:
        return f"{self.registry_name()}_civmc.png".lower().replace("_", " ")

    @staticmethod
    def extract_coords(filename: str) -> tuple[int, int]:
        match = search(r"_x(-?\d+)_z(-?\d+)\.png$", filename)
        if not match:
            raise ValueError(f"Filename '{filename}' does not match expected pattern")
        return tuple(map(int, match.groups()))


class LandRegistryEntry(BaseModel):
    shape: Shape
    owner: str
    date: datetime
    type: ZoneType
    name: str | None = None
    address: str | None = None
    details: str | None = None

    @field_validator("shape", mode="before")
    @classmethod
    def parse_shape(cls, v: object) -> Shape:
        if not isinstance(v, str):
            for shape_type in Shape.__subclasses__():
                try:
                    return shape_type.model_validate(v)
                except ValueError:
                    continue
            raise ValueError(
                f"No valid shape type found for data: {v}. "
                f"Supported types are: {', '.join(t.__name__ for t in Shape.__subclasses__())}"
            )
        coords = [int(value) for value in v.split(" ")]
        if len(coords) == 4:
            return Rect(
                p1=Point(x=coords[0], z=coords[1]),
                p2=Point(x=coords[2], z=coords[3]),
            )
        elif len(coords) == 3:
            return Circle(center=Point(x=coords[0], z=coords[1]), radius=coords[2])
        elif len(coords) > 5 and len(coords) % 2 == 0:
            return Polygon(
                points=[Point(x=x, z=z) for x, z in zip(coords[::2], coords[1::2])]
            )
        raise ValueError(f"No valid shape type found for data: {v}.")

    def get_wiki_imagemap_entry(self, offset_x: int, offset_y: int) -> str:
        link = (
            f"[[{{{{PAGENAME}}}}#{self.name}|{self.name}]]"
            if self.name is not None
            else f"[[{self.owner}|]]"
        )
        return f"{self.shape.get_wiki_imagemap_str(offset_x, offset_y)} {link}"


class LandRegistry(BaseModel):
    files: LandRegistryFile
    entries: list[LandRegistryEntry]

    def generate_wiki_imagemap(
        self,
    ) -> str:
        registry_data = "\n".join(
            entry.get_wiki_imagemap_entry(self.files.offset_x, self.files.offset_y)
            for entry in self.entries
        )
        return (
            "{{#tag:imagemap|\n"
            f"Image:{self.files.image_map_name()} {{{{!}}}}{{{{{{1|640px}}}}}}\n"
            f"{registry_data}\n"
            "}}"
        )

    def generate_land_ownership_table(self) -> str:
        writer = MediaWikiTableWriter()
        table_data: dict[str, tuple[str, int, int | float]] = {}
        for entry in self.entries:
            owners = entry.owner.split(", ")
            parsed_owners = [owner.lower() for owner in owners]
            for owner, parsed_owner in zip(owners, parsed_owners):
                if parsed_owner not in table_data:
                    table_data[parsed_owner] = (f"[[{owner}]]", 0, 0)
                _, buildings_owned, land_owned = table_data[parsed_owner]
                table_data[parsed_owner] = (
                    f"[[{owner}]]",
                    buildings_owned + 1,
                    round(land_owned + entry.shape.area() / len(owners), 2),
                )
        matrix_data = [
            list(v) for v in sorted(table_data.values(), key=lambda x: x[0].lower())
        ]
        writer.headers = ["Owner", "Amount of Buildings Owned", "Total Land Owned (m²)"]
        writer.value_matrix = matrix_data
        return writer.dumps().replace("wikitable", "wikitable sortable", 1)

    def generate_pie_chart_zoning_type(self) -> str:
        d = self.get_land_zoning_distribution()
        labels = list(d.keys())
        values = list(d.values())

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0,
                    marker=dict(
                        colors=[k.color() for k in labels],
                        line=dict(color="white", width=2),
                    ),
                    textinfo="percent",
                    textfont=dict(
                        size=16, color="white", family="Roboto, Arial, sans-serif"
                    ),
                    texttemplate='<span style="text-shadow:1px 1px 2px black;">%{percent}</span>',
                )
            ]
        )

        fig.update_layout(
            title=dict(
                text=f"Land Usage Distribution ({self.files.registry_name().title()})",
                x=0.5,
                font=dict(size=26, family="Roboto, Arial, sans-serif", color="#333"),
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.15,
                xanchor="center",
                x=0.5,
                font=dict(size=14, family="Roboto, Arial, sans-serif"),
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            margin=dict(t=80, b=10, l=0, r=0),
        )
        file_name = f"land_usage_distribution_{self.files.registry_name().replace(' ', '_')}.svg"
        fig.write_image(
            join(
                self.files.path,
                file_name,
            ),
            format="svg",
            scale=1,
        )
        return file_name

    def aggregate_and_sort(
        self,
        entries,
        key_func: Callable[[Any], Any],
        value_func: Callable[[Any], float] = lambda e: 1,
        to_percentage: bool = False,
    ) -> dict:
        agg = {}
        total = 0
        for entry in entries:
            k = key_func(entry)
            v = value_func(entry)
            if k not in agg:
                agg[k] = 0
            agg[k] += v
            total += v

        if to_percentage and total > 0:
            agg = {k: round(v * 100 / total, 2) for k, v in agg.items()}

        return dict(sorted(agg.items(), key=lambda x: x[1], reverse=True))

    def get_landowners_sorted(self):
        return self.aggregate_and_sort(
            self.entries,
            key_func=lambda e: e.owner,
            value_func=lambda e: e.shape.area(),
        )

    def get_land_zoning_distribution(self) -> dict["ZoneType", float]:
        return self.aggregate_and_sort(
            self.entries,
            key_func=lambda e: e.type,
            value_func=lambda e: e.shape.area(),
            to_percentage=True,
        )

import json
import os
import logging
import wikitextparser as wtp

from models import LandRegistryFile, LandRegistryEntry, LandRegistry
from mwclient import Site
from mwclient.image import Image
from wikitextparser import Section
from hashlib import sha1

logging.root.setLevel(logging.INFO)

def find_land_registry_files(base_path: str = ".") -> list[LandRegistryFile]:
    results: list[LandRegistryFile] = []

    for entry in os.listdir(base_path):
        dir_path = os.path.join(base_path, entry)
        if not os.path.isdir(dir_path):
            continue

        json_files = [f for f in os.listdir(dir_path) if f.endswith(".json")]
        image_files = [f for f in os.listdir(dir_path) if f.endswith(".png")]

        if not json_files or not image_files:
            logging.error(f"File {entry} did not have json file or image file")
            continue  # Skip if either file is missing

        json_path = os.path.join(dir_path, json_files[0])
        image_path = os.path.join(dir_path, image_files[0])

        offset_x, offset_y = LandRegistryFile.extract_coords(image_files[0])

        results.append(
            LandRegistryFile(
                path=dir_path,
                data_file=json_path,
                image_file=image_path,
                offset_x=offset_x,
                offset_y=offset_y,
            )
        )

    return results


def upload_image_if_it_has_changes(
    site: Site,
    image_name: str,
    image_path: str = ".",
    alternative_file_src: str | None = None,
):
    """Upload an image only if it doesn't exist or has changed."""
    site_image = site.images[image_name]
    file_src = alternative_file_src if alternative_file_src is not None else image_name
    with open(os.path.join(image_path, file_src), "rb") as image:
        local_sha1 = sha1(image.read()).hexdigest()

        if not site_image.exists or "sha1" not in site_image.imageinfo:
            logging.info(f"Uploading new image: {image_name}")
            site.upload(image, image_name, "Initial upload")
            return

        lastest_sha1 = site_image.imageinfo["sha1"]

        if lastest_sha1 == local_sha1:
            logging.info(
                f"'{image_name}' is identical to the latest version — skipping upload."
            )
        else:
            logging.info(f"'{image_name}' differs — uploading new version.")
            site.upload(image, image_name, "Updated image", ignore=True)


def update_interactive_map(
    site: Site, registry: LandRegistry, name: str, changes: list[str], section: Section
):
    upload_image_if_it_has_changes(
        site,
        registry.files.image_map_name(),
        alternative_file_src=registry.files.image_file,
    )
    section.contents = f"{registry.generate_wiki_imagemap()}\n"
    changes.append("Updated interactive map")


def update_land_ownership(
    site: Site, registry: LandRegistry, name: str, changes: list[str], section: Section
):
    pie_chart_land_usage = registry.generate_pie_chart_zoning_type()
    upload_image_if_it_has_changes(site, pie_chart_land_usage, registry.files.path)
    land_usage_pie_chart_file_wiki_markup = f"[[File:{pie_chart_land_usage}|thumb|Land usage in {name.title()} by Zoning type|400x400px]]"
    section.contents = f"{land_usage_pie_chart_file_wiki_markup}\n{registry.generate_land_ownership_table()}\n"
    changes.append("Updated land ownership table")


def main():
    logging.info("Logging in to civwiki.org")
    site = Site(
        "civwiki.org", clients_useragent="LusitaniaBot/1.0.0 (metriximor@gmail.com)"
    )
    site.login(os.getenv("CIVWIKI_USERNAME"), os.getenv("CIVWIKI_PASSWORD"))
    logging.info("Logged in to civwiki.org")

    # Load data
    land_registries: dict[str, LandRegistry] = {}
    for registry in find_land_registry_files("../../../land_registry"):
        land_registry = []
        with open(registry.data_file, "r", encoding="UTF-8") as land_ownership_file:
            unparsed_land_ownership = json.loads(land_ownership_file.read())
            for entry in unparsed_land_ownership:
                land_registry.append(LandRegistryEntry.model_validate(entry))
        land_registries[registry.registry_name()] = LandRegistry(
            files=registry, entries=land_registry
        )
        logging.info(f"Parsed {registry.data_file}")

    # Update the wiki
    for name, registry in land_registries.items():
        logging.info(f"Updating {name} page data")
        page = site.pages[f"{name.title()} (CivMC)"]
        content = wtp.parse(page.text())
        changes = []
        for section in content.get_sections(include_subsections=False):
            if section.title is None:
                continue
            if "Interactive Map" in section.title:
                update_interactive_map(site, registry, name, changes, section)
            if "Land Ownership" in section.title:
                update_land_ownership(site, registry, name, changes, section)
        # print(content.string)
        page.edit(content.string, ", ".join(changes))


if __name__ == "__main__":
    main()

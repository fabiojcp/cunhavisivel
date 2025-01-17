from pathlib import Path
import time
import uuid
import click
from loguru import logger

from cunha_visivel.utils.utils import generateId
from cunha_visivel.workdir.operator import WorkdirOperator
from cunha_visivel.workdir.structs import CunhaVisivelDB
from cunha_visivel.workdir.structs_mysql import RelationalDB


@click.command()
@click.argument("workdir", type=click.Path(), required=False)
@click.option(
    "--invert", is_flag=True, help="Generate inverted index from Pages table in MySQL."
)
def sync_cli(workdir: str, invert: bool) -> None:
    # Conectar ao banco de dados MySQL
    db = RelationalDB()
    # db.print_tables()
    # return

    if invert:
        db.invert_index()
        logger.success("Inverted index generated!")
        return

    if not workdir:
        logger.error("Workdir path is required. try --help for more information.")
        return

    workdir_path = Path(workdir).absolute()

    if ".workdir" not in workdir_path.suffix:
        workdir_path = Path(str(workdir_path) + ".workdir").absolute()

    if not workdir_path.exists():
        logger.error(f"Directory {workdir_path} does not exist.")
        return

    json_path = workdir_path / "db.json"

    if not json_path.exists():
        logger.error(f"File {json_path} does not exist.")
        return

    # Carregar o banco de dados JSON
    cunha_db = CunhaVisivelDB.model_validate_json(json_path.read_text())

    # Sincronizar o banco de dados
    for url, pdf_info in cunha_db.pdf_links.items():
        newId = str(uuid.uuid4())
        inserted = db.insert_pdf_info(newId, url, pdf_info)
        time.sleep(0.001)
        if inserted:
            pdf_id = db.get_pdf_id(url)
            db.insert_pdf_pages(pdf_id, pdf_info.pages)
            logger.info(f"Inserted PDF {url} and its pages into the database.")
        else:
            logger.info(f"PDF {url} already exists in the database, skipping.")

    logger.success("Database synchronization complete!")


if __name__ == "__main__":
    sync_cli()

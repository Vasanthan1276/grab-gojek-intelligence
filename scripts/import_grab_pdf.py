from __future__ import annotations

import re
from datetime import datetime

import fitz
import pandas as pd
import pytesseract

from PIL import Image
from pytesseract import Output

from normalization import normalize_location


BASE_W = 1870
BASE_H = 2420


# ============================================================
# PDF RENDERING
# ============================================================

def _render(pdf_path):
    """
    Render every PDF page into a high-resolution image
    for OCR processing.
    """

    document = fitz.open(pdf_path)

    images = []

    zoom = 220 / 72

    matrix = fitz.Matrix(
        zoom,
        zoom
    )

    for page in document:

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False
        )

        image = Image.frombytes(
            "RGB",
            [
                pixmap.width,
                pixmap.height
            ],
            pixmap.samples
        )

        images.append(
            image
        )

    return images


# ============================================================
# OCR HELPER
# ============================================================

def _data(
    image,
    psm=6
):
    """
    Run OCR and return recognised words
    with their positions.
    """

    dataframe = pytesseract.image_to_data(
        image,
        config=f"--psm {psm}",
        output_type=Output.DATAFRAME
    )

    dataframe = dataframe[
        (
            dataframe.conf >= 0
        )
        &
        dataframe.text.notna()
    ].copy()

    return dataframe


# ============================================================
# DATE / TIME EXTRACTION
# ============================================================

def _date_rows(
    image,
    first_page
):
    """
    Extract transaction date/time rows.

    Tesseract can occasionally merge the end of one Grab transaction
    timestamp with the beginning of the next transaction into a single
    OCR line. This parser extracts all date and time tokens in reading
    order instead of assuming one clean date line followed by one clean
    time line.
    """

    width, height = image.size

    y0 = int(
        height
        *
        (
            440 / BASE_H
            if first_page
            else 55 / BASE_H
        )
    )

    crop = image.crop(
        (
            int(width * 115 / BASE_W),
            y0,
            int(width * 315 / BASE_W),
            height
        )
    )

    crop = crop.resize(
        (
            400,
            (height - y0) * 2
        )
    )

    dataframe = _data(
        crop,
        6
    )

    lines = []

    for _, group in dataframe.groupby(
        [
            "block_num",
            "par_num",
            "line_num"
        ]
    ):
        group = group.sort_values(
            "left"
        )

        text = " ".join(
            group.text.astype(str)
        )

        top = float(
            group.top.min()
        )

        bottom = float(
            (group.top + group.height).max()
        )

        lines.append(
            (
                top,
                bottom,
                text
            )
        )

    lines.sort(
        key=lambda item: item[0]
    )

    date_pattern = re.compile(
        r"\b(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\b",
        re.I
    )

    time_pattern = re.compile(
        r"\b(\d{1,2}:\d{2})\s*(AM|PM)\b",
        re.I
    )

    events = []

    for top, bottom, text in lines:
        line_center = (top + bottom) / 2

        for match in date_pattern.finditer(text):
            events.append(
                {
                    "kind": "date",
                    "position": match.start(),
                    "line_top": top,
                    "line_center": line_center,
                    "text": (
                        f"{match.group(1)} "
                        f"{match.group(2).title()} "
                        f"{match.group(3)}"
                    )
                }
            )

        for match in time_pattern.finditer(text):
            events.append(
                {
                    "kind": "time",
                    "position": match.start(),
                    "line_top": top,
                    "line_center": line_center,
                    "text": (
                        f"{match.group(1)}"
                        f"{match.group(2).upper()}"
                    )
                }
            )

    events.sort(
        key=lambda item: (
            item["line_top"],
            item["position"]
        )
    )

    output = []
    pending_date = None

    for event in events:
        if event["kind"] == "date":
            pending_date = event
            continue

        if event["kind"] != "time" or pending_date is None:
            continue

        datetime_text = (
            pending_date["text"]
            +
            " "
            +
            event["text"]
        )

        try:
            datetime_value = datetime.strptime(
                datetime_text,
                "%d %b %Y %I:%M%p"
            )
        except ValueError:
            pending_date = None
            continue

        center = (
            y0
            +
            (
                (
                    pending_date["line_center"]
                    +
                    event["line_center"]
                )
                /
                2
            )
            /
            2
        )

        output.append(
            (
                datetime_value,
                center
            )
        )

        pending_date = None

    return output

# ============================================================
# AMOUNT EXTRACTION
# ============================================================

def _amounts(
    image,
    first_page
):
    """
    Extract transaction amounts.
    """

    width, height = (
        image.size
    )

    y0 = int(
        height
        *
        (
            440 / BASE_H
            if first_page
            else 55 / BASE_H
        )
    )

    crop = image.crop(
        (
            int(
                width
                *
                1655
                /
                BASE_W
            ),
            y0,
            int(
                width
                *
                1795
                /
                BASE_W
            ),
            height
        )
    )

    crop = crop.resize(
        (
            420,
            (
                height
                -
                y0
            )
            *
            3
        )
    )

    dataframe = _data(
        crop,
        6
    )

    values = []

    for text in (
        dataframe
        .text
        .astype(str)
    ):

        match = re.search(
            r"\d+(?:\.\d+)?",
            text
        )

        if match:

            values.append(
                float(
                    match.group()
                )
            )

    return values


# ============================================================
# GRAB SERVICE CLASSIFICATION
# ============================================================

def _service(
    raw_service
):
    """
    Convert the raw Grab service description
    into consistent analytical fields.

    Returns:

        service
        category
        pricing_type

    pricing_type values:

        Fixed
        Metered
        Premium
        Food
    """

    cleaned = re.sub(
        r"\s+",
        " ",
        str(
            raw_service
            or ""
        )
    ).strip()

    upper = (
        cleaned.upper()
    )


    # --------------------------------------------------------
    # FOOD
    # --------------------------------------------------------

    if (
        "GRABFOOD"
        in upper

        or

        "GRABOOD"
        in upper
    ):

        return (
            "GrabFood",
            "food",
            "Food"
        )


    # --------------------------------------------------------
    # METERED TAXI
    #
    # This must be checked before generic "Standard"
    # because Grab may describe the service as:
    #
    # Standard | Metered taxi only
    # --------------------------------------------------------

    if (
        "METERED"
        in upper
    ):

        return (
            "Metered Taxi",
            "ride",
            "Metered"
        )


    # --------------------------------------------------------
    # PREMIUM / PLUS
    # --------------------------------------------------------

    if (
        "PLUS"
        in upper

        or

        "PREMIUM"
        in upper
    ):

        return (
            "Standard Plus",
            "ride",
            "Premium"
        )


    # --------------------------------------------------------
    # JUSTGRAB
    # --------------------------------------------------------

    if (
        "JUSTGRAB"
        in upper
    ):

        return (
            "JustGrab",
            "ride",
            "Fixed"
        )


    # --------------------------------------------------------
    # STANDARD 4-SEATER
    # --------------------------------------------------------

    if (
        "4 SEATER"
        in upper

        or

        "4-SEATER"
        in upper
    ):

        return (
            "Standard 4-seater",
            "ride",
            "Fixed"
        )


    # --------------------------------------------------------
    # STANDARD CAR OR TAXI
    # --------------------------------------------------------

    if (
        "CAR OR TAXI"
        in upper
    ):

        return (
            "Standard Car or Taxi",
            "ride",
            "Fixed"
        )


    # --------------------------------------------------------
    # GENERIC STANDARD
    # --------------------------------------------------------

    return (
        "Standard",
        "ride",
        "Fixed"
    )


# ============================================================
# MAIN GRAB IMPORT
# ============================================================

def import_grab_pdf(
    pdf_path,
    aliases=None
):
    """
    Import Grab Member Statement PDF transactions.

    New fields retained:

        raw_service
        service
        pricing_type

    Example:

        raw_service:
            Standard | Metered taxi only

        service:
            Metered Taxi

        pricing_type:
            Metered
    """

    records = []

    images = _render(
        pdf_path
    )


    for (
        page_index,
        image
    ) in enumerate(
        images
    ):

        first_page = (
            page_index
            ==
            0
        )


        date_rows = _date_rows(
            image,
            first_page
        )


        amounts = _amounts(
            image,
            first_page
        )


        if (
            len(date_rows)
            !=
            len(amounts)
        ):

            raise RuntimeError(

                "OCR row mismatch "
                f"on page {page_index + 1}: "
                f"{len(date_rows)} dates "
                f"vs "
                f"{len(amounts)} amounts"

            )


        dataframe = _data(
            image,
            6
        )


        dataframe[
            "yc"
        ] = (
            dataframe.top
            +
            dataframe.height
            /
            2
        )


        width, height = (
            image.size
        )


        centers = [

            center

            for (
                _,
                center
            )

            in date_rows

        ]


        if (
            len(centers)
            >
            1
        ):

            bounds = [

                centers[0]
                -
                (
                    centers[1]
                    -
                    centers[0]
                )
                /
                2

            ]


            bounds += [

                (
                    centers[index]
                    +
                    centers[index + 1]
                )
                /
                2

                for index in range(
                    len(centers)
                    -
                    1
                )

            ]


            bounds += [

                centers[-1]
                +
                (
                    centers[-1]
                    -
                    centers[-2]
                )
                /
                2

            ]


        else:

            bounds = [
                0,
                height
            ]


        columns = {

            "pickup":
                (
                    520,
                    930
                ),

            "dropoff":
                (
                    930,
                    1350
                ),

            "service":
                (
                    1350,
                    1570
                ),

            "currency":
                (
                    1570,
                    1665
                )

        }


        for (
            index,
            (
                datetime_value,
                _
            )
        ) in enumerate(
            date_rows
        ):


            row = dataframe[
                (
                    dataframe.yc
                    >=
                    bounds[index]
                )
                &
                (
                    dataframe.yc
                    <
                    bounds[index + 1]
                )
            ]


            parsed = {}


            for (
                column_name,
                (
                    start,
                    end
                )
            ) in columns.items():


                scaled_start = int(
                    width
                    *
                    start
                    /
                    BASE_W
                )


                scaled_end = int(
                    width
                    *
                    end
                    /
                    BASE_W
                )


                words = row[
                    (
                        row.left
                        >=
                        scaled_start
                    )
                    &
                    (
                        row.left
                        <
                        scaled_end
                    )
                ]


                words = (
                    words
                    .sort_values(
                        [
                            "top",
                            "left"
                        ]
                    )
                )


                parsed[
                    column_name
                ] = " ".join(

                    words
                    .text
                    .astype(str)

                ).strip()


            raw_service = (
                parsed[
                    "service"
                ]
            )


            (
                service,
                category,
                pricing_type
            ) = _service(
                raw_service
            )


            currency = (

                "MYR"

                if

                "MYR"
                in
                parsed[
                    "currency"
                ].upper()

                else

                "SGD"

            )


            origin = normalize_location(

                parsed[
                    "pickup"
                ],

                aliases

            )


            destination = normalize_location(

                parsed[
                    "dropoff"
                ],

                aliases

            )


            if (

                category
                ==
                "food"

                and

                destination
                not in
                {
                    "HOME",
                    "OFFICE",
                    "V_PLACE",
                    "COMPASSVALE"
                }

            ):

                destination = (

                    "OTHER_DELIVERY_LOCATION"

                )


            records.append(
                {

                    "datetime":
                        datetime_value.isoformat(
                            timespec="minutes"
                        ),

                    "date":
                        datetime_value
                        .date()
                        .isoformat(),

                    "time":
                        datetime_value.strftime(
                            "%H:%M"
                        ),

                    "hour":
                        datetime_value.hour,

                    "weekday":
                        datetime_value.strftime(
                            "%A"
                        ),

                    "provider":
                        "Grab",

                    "category":
                        category,

                    "raw_service":
                        raw_service,

                    "service":
                        service,

                    "pricing_type":
                        pricing_type,

                    "origin":
                        origin,

                    "destination":
                        destination,

                    "amount":
                        round(
                            amounts[index],
                            2
                        ),

                    "currency":
                        currency

                }
            )


    return records

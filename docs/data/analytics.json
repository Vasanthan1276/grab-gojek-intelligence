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
                115
                /
                BASE_W
            ),
            y0,
            int(
                width
                *
                315
                /
                BASE_W
            ),
            height
        )
    )

    crop = crop.resize(
        (
            400,
            (
                height
                -
                y0
            )
            *
            2
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
            group.text.astype(
                str
            )
        )

        lines.append(
            (
                float(
                    group.top.min()
                ),
                float(
                    (
                        group.top
                        +
                        group.height
                    ).max()
                ),
                text
            )
        )

    lines.sort()

    output = []

    index = 0

    while index < (
        len(lines)
        -
        1
    ):

        date_text = (
            lines[index][2]
            .strip()
        )

        time_text = (
            lines[index + 1][2]
            .strip()
        )

        date_match = re.match(
            r"\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}",
            date_text
        )

        time_match = re.search(
            r"\d{1,2}:\d{2}(?:AM|PM)",
            time_text,
            re.I
        )

        if (
            date_match
            and
            time_match
        ):

            datetime_value = datetime.strptime(
                (
                    re.sub(
                        r",$",
                        "",
                        date_text
                    )
                    +
                    " "
                    +
                    time_text.upper()
                ),
                "%d %b %Y %I:%M%p"
            )

            center = (
                y0
                +
                (
                    (
                        lines[index][0]
                        +
                        lines[index + 1][1]
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

            index += 2

        else:

            index += 1

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

"""Module for image services."""

import logging

import requests
from google.cloud import vision
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout


class AiImageService:
    """Class representing image services."""

    def analyze_photo_with_google_detailed(self, image_uri: str) -> dict:
        """Send infile to Google Vision API, return dict with all labels, objects and texts."""
        logging.debug("Enter Google vision API")
        _tags = {}

        # Instantiates a client
        client = vision.ImageAnnotatorClient()
        image = vision.Image()
        image.source.image_uri = image_uri

        # Performs label detection on the image file
        response = client.label_detection(image=image)  # type: ignore[no-untyped-call]
        labels = response.label_annotations
        for label in labels:
            logging.debug(f"Found label: {label.description}")
            _tags["Label"] = label.description

        # Performs object detection on the image file
        objects = client.object_localization(image=image).localized_object_annotations  # type: ignore[no-untyped-call]
        for object_ in objects:
            logging.debug(
                f"Found object: {object_.name} (confidence: {object_.score})"
            )
            _tags["Object"] = object_.name

        # Performs text detection on the image file
        response = client.document_text_detection(image=image)  # type: ignore[no-untyped-call]
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                logging.debug(f"\nBlock confidence: {block.confidence}\n")

                for paragraph in block.paragraphs:
                    logging.debug(
                        f"Paragraph confidence: {paragraph.confidence}"
                    )

                    for word in paragraph.words:
                        word_text = "".join([symbol.text for symbol in word.symbols])
                        logging.debug(
                            f"Word text: {word_text} (confidence: {word.confidence})"
                        )

                        for symbol in word.symbols:
                            logging.debug(
                                f"\tSymbol: {symbol.text} (confidence: {symbol.confidence})"
                            )

        if response.error.message:
            err_msg = f"{response.error.message}, see: https://cloud.google.com/apis/design/errors"
            raise Exception(err_msg)

        return _tags

    def analyze_photo_g_langrenn_v2(
        self, image_uri: str, crop_uri: str, conf_limit: str
    ) -> dict:
        """Send infile to Vision API, return dict with langrenn info."""
        logging.info(f"Enter vision, image {image_uri}")
        _tags = {
            "persons": 0,
            "ai_numbers": [],
            "ai_text": [],
            "ai_crop_numbers": [],
            "ai_crop_text": [],
        }

        try:
            # Instantiates a client
            client = vision.ImageAnnotatorClient()  # type: ignore[no-untyped-call]
            # Loads the image into memory
            content = requests.get(image_uri, timeout=5).content
            image = vision.Image(content=content)  # type: ignore[no-untyped-call]
            content_crop = requests.get(crop_uri, timeout=5).content
            image_crop = vision.Image(content=content_crop)  # type: ignore[no-untyped-call]
        except Timeout as e:
            err_msg = "Timeout when connecting to VisionAI service"
            logging.exception(err_msg)
            raise Exception(err_msg) from e
        except RequestsConnectionError as e:
            err_msg = "Kunne ikke koble til GoogleVisionAI"
            logging.exception(err_msg)
            raise Exception(err_msg) from e

        # Performs object detection on the image file
        _tags["persons"] = self.detect_persons(client, image, conf_limit)

        # Performs text detection on the image file
        _tags["ai_numbers"], _tags["ai_text"] = self.detect_text(client, image, conf_limit)
        _tags["ai_crop_numbers"], _tags["ai_crop_text"] = self.detect_text(client, image_crop, conf_limit)
        return _tags


    def detect_persons(self, client: vision.ImageAnnotatorClient, image: vision.Image, conf_limit: str) -> int:
        """Detect persons in the image."""
        objects = client.object_localization(image=image).localized_object_annotations  # type: ignore[no-untyped-call]
        count_persons = 0
        for object_ in objects:
            logging.debug(
                f"Found object: {object_.name} (confidence: {object_.score})"
            )
            if float(conf_limit) < object_.score:
                if object_.name == "Person":
                    count_persons += 1
        return count_persons


    def detect_text(self, client: vision.ImageAnnotatorClient, image: vision.Image, conf_limit: str) -> tuple:
        """Detect text in the image."""
        _numbers = []
        _texts = []
        response = client.document_text_detection(image=image)  # type: ignore[no-untyped-call]
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        if float(conf_limit) < word.confidence:
                            word_text = "".join(
                                [symbol.text for symbol in word.symbols]
                            )
                            logging.debug(
                                f"Word text: {word_text} (confidence: {word.confidence})"
                            )
                            if word_text.isnumeric():
                                _numbers.append(int(word_text))
                            else:
                                _texts.append(word_text)
        if response.error.message:
            err_msg = f"{response.error.message}, see: https://cloud.google.com/apis/design/errors"
            raise Exception(err_msg)
        return _numbers, _texts

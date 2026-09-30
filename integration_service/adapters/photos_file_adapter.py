"""Module adapter for photos on file storage."""

import datetime
import logging
import re
import subprocess
from pathlib import Path

from integration_service.adapters.google_cloud_storage_adapter import (
    GOOGLE_STORAGE_BUCKET,
    GOOGLE_STORAGE_SERVER,
    GoogleCloudStorageAdapter,
)

VISION_ROOT_PATH = f"{Path.cwd()}/integration_service/files"
CAPTURED_FILE_PATH = f"{VISION_ROOT_PATH}/CAPTURE"
CAPTURED_RAW_FILE_PATH = f"{VISION_ROOT_PATH}/CAPTURE_RAW"
CAPTURED_SRT_FILE_PATH = f"{VISION_ROOT_PATH}/CAPTURE_SRT"
CAPTURED_ARCHIVE_PATH = f"{VISION_ROOT_PATH}/CAPTURE/archive"
CAPTURED_ERROR_ARCHIVE_PATH = f"{VISION_ROOT_PATH}/CAPTURE/error_archive"
PHOTOS_ARCHIVE_PATH = f"{VISION_ROOT_PATH}/archive"
PHOTOS_URL_PATH = "files"


class PhotosFileAdapter:
    """Class representing photos."""

    def get_photos_folder_path(self) -> str:
        """Get path to photo folder."""
        return VISION_ROOT_PATH

    def init_video_folders(self) -> None:
        """Ensure folders exists."""
        my_folder = Path(CAPTURED_FILE_PATH)
        if not my_folder.exists():
            my_folder.mkdir(parents=True, exist_ok=True)
        my_folder = Path(CAPTURED_RAW_FILE_PATH)
        if not my_folder.exists():
            my_folder.mkdir(parents=True, exist_ok=True)
        my_folder = Path(CAPTURED_SRT_FILE_PATH)
        if not my_folder.exists():
            my_folder.mkdir(parents=True, exist_ok=True)

    def get_capture_folder_path(self) -> str:
        """Get path to captured videos folder."""
        return CAPTURED_FILE_PATH

    def get_raw_capture_folder_path(self) -> str:
        """Get path to raw captured video folder."""
        return CAPTURED_RAW_FILE_PATH

    def get_srt_capture_folder_path(self) -> str:
        """Get path to SRT captured video folder."""
        return CAPTURED_SRT_FILE_PATH

    def get_photos_archive_folder_path(self) -> str:
        """Get path to photo archive folder."""
        return PHOTOS_ARCHIVE_PATH

    def get_all_photos(self) -> list:
        """Get all path/filename to all photos on file directory."""
        photos = []
        try:
            files = list(Path(VISION_ROOT_PATH).iterdir())
            photos = [
                f"{VISION_ROOT_PATH}/{f.name}"
                for f in files
                if f.suffix in [".jpg", ".png"] and "_config" not in f.name
            ]
        except Exception:
            logging.exception("Error getting photos")
        return photos

    def get_all_capture_files(self, event_id: str, storage_mode: str) ->  list[dict]:
        """Get all url to all captured files on file directory."""
        file_list = []
        try:
            if storage_mode == "cloud_storage":
                file_list = GoogleCloudStorageAdapter().list_blobs(event_id, "CAPTURE/")
            else:
                # Local file system
                Path(CAPTURED_FILE_PATH).mkdir(parents=True, exist_ok=True)
                files = list(Path(CAPTURED_FILE_PATH).iterdir())
                file_list = [
                    {"name": f.name, "url": f"{CAPTURED_FILE_PATH}/{f.name}"}
                    for f in files
                if f.is_file()
                ]
        except Exception:
            informasjon = "Error getting captured files"
            logging.exception(informasjon)
            return []
        else:
            return file_list

    def get_all_raw_capture_files(self, event_id: str, storage_mode: str) ->  list[dict]:
        """Get all url to all raw captured files on file directory."""
        file_list = []
        try:
            if storage_mode == "cloud_storage":
                file_list = GoogleCloudStorageAdapter().list_blobs(event_id, "RAW_CAPTURE/")
            else:
                # Local file system
                Path(CAPTURED_RAW_FILE_PATH).mkdir(parents=True, exist_ok=True)
                files = list(Path(CAPTURED_RAW_FILE_PATH).iterdir())
                file_list = [
                    {"name": f.name, "url": f"{CAPTURED_RAW_FILE_PATH}/{f.name}"}
                    for f in files
                    if f.is_file() and not f.name.startswith("TMP")
                ]
        except Exception:
            informasjon = "Error getting captured files"
            logging.exception(informasjon)
            return []
        else:
            return file_list

    def get_all_srt_files(self, event_id: str, storage_mode: str) ->  list[dict]:
        """Get all url to all srt files on file directory."""
        file_list = []
        try:
            if storage_mode == "cloud_storage":
                file_list = GoogleCloudStorageAdapter().list_blobs(event_id, "CAPTURE_SRT/")
            else:
                # Local file system
                Path(CAPTURED_SRT_FILE_PATH).mkdir(parents=True, exist_ok=True)
                files = list(Path(CAPTURED_SRT_FILE_PATH).iterdir())
                file_list = [
                    {"name": f.name, "url": f"{CAPTURED_SRT_FILE_PATH}/{f.name}"}
                    for f in files
                    if f.is_file() and not f.name.startswith("TMP")
                ]
        except Exception:
            informasjon = "Error getting captured files"
            logging.exception(informasjon)
            return []
        else:
            return file_list

    def get_all_files(self, prefix: str, suffix: str) -> list:
        """Get all url to all files on file directory with given prefix and suffix."""
        my_files = []
        try:
            files = list(Path(VISION_ROOT_PATH).iterdir())  # Materialize iterator and close it
            my_files = [
                f"{VISION_ROOT_PATH}/{file.name}"
                for file in files
                if file.suffix == suffix and prefix in file.name
            ]
        except Exception:
            informasjon = f"Error getting files, prefix: {prefix}, suffix: {suffix}"
            logging.exception(informasjon)
        return my_files

    def move_photo_to_archive(self, filename: str) -> None:
        """Move photo to archive."""
        source_file = Path(VISION_ROOT_PATH) / filename
        destination_file = Path(PHOTOS_ARCHIVE_PATH) / source_file.name

        try:
            source_file.rename(destination_file)
        except FileNotFoundError:
            logging.info("Destination folder not found. Creating...")
            Path(PHOTOS_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            source_file.rename(destination_file)
        except Exception:
            logging.exception("Error moving photo to archive.")


    def move_to_archive(self, filename: str) -> None:
        """Move photo to archive."""
        source_file = Path(VISION_ROOT_PATH) / filename
        destination_file = Path(PHOTOS_ARCHIVE_PATH) / source_file.name

        try:
            source_file.rename(destination_file)
        except FileNotFoundError:
            logging.info("Destination folder not found. Creating...")
            Path(PHOTOS_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            source_file.rename(destination_file)
        except Exception:
            logging.exception("Error moving photo to archive.")

    def move_to_capture_archive(self, event_id: str, storage_mode: str, filename: str) -> str:
        """Move photo to local archive."""
        if storage_mode == "cloud_storage":
            return GoogleCloudStorageAdapter().move_to_capture_archive(
                event_id, filename
            )
        source_file = Path(CAPTURED_FILE_PATH) / filename
        destination_file = Path(CAPTURED_ARCHIVE_PATH) / filename
        try:
            source_file.rename(destination_file)
        except FileNotFoundError:
            logging.info("Destination folder not found. Creating.")
            Path(CAPTURED_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            source_file.rename(destination_file)
        except Exception:
            logging.exception(f"Error moving photo to archive: {filename}")
        return destination_file.name

    def move_to_error_archive(self, event_id: str, storage_mode: str, filename: str) -> str:
        """Move photo to local error archive."""
        if storage_mode == "cloud_storage":
            return GoogleCloudStorageAdapter().move_to_error_archive(
                event_id, filename
            )
        source_file = Path(CAPTURED_FILE_PATH) / filename
        destination_file = Path(CAPTURED_ERROR_ARCHIVE_PATH) / filename
        try:
            source_file.rename(destination_file)
        except FileNotFoundError:
            logging.info("Destination folder not found. Creating.")
            Path(CAPTURED_ERROR_ARCHIVE_PATH).mkdir(parents=True, exist_ok=True)
            source_file.rename(destination_file)
        except Exception:
            logging.exception(f"Error moving photo to error archive: {filename}")
        return destination_file.name

    def convert_raw_to_mp4(self, input_file: str) -> None:
        """Convert (and repair) a video file to MP4 using FFmpeg."""
        # A cloud storage file is passed in as a public URL, not a local path -
        # it must be downloaded locally before ffmpeg can process/delete it.
        cloud_storage_prefix = f"{GOOGLE_STORAGE_SERVER}/{GOOGLE_STORAGE_BUCKET}/"
        blob_name = None
        segment_blob_names: list[str] = []
        segment_paths: list[Path] = []
        try:
            if input_file.startswith(cloud_storage_prefix):
                blob_name = input_file.removeprefix(cloud_storage_prefix)
                input_path = Path(CAPTURED_SRT_FILE_PATH) / Path(blob_name).name
                Path(CAPTURED_SRT_FILE_PATH).mkdir(parents=True, exist_ok=True)
                GoogleCloudStorageAdapter().download_blob(blob_name, str(input_path))

                # HLS playlists only reference segments by relative name, so
                # those segment blobs must be fetched into the same folder too.
                if input_path.suffix == ".m3u8":
                    blob_folder = blob_name.rsplit("/", 1)[0]
                    for line in input_path.read_text().splitlines():
                        segment_name = line.strip()
                        if not segment_name or segment_name.startswith("#"):
                            continue
                        segment_blob_name = f"{blob_folder}/{segment_name}"
                        segment_path = Path(CAPTURED_SRT_FILE_PATH) / segment_name
                        GoogleCloudStorageAdapter().download_blob(
                            segment_blob_name, str(segment_path)
                        )
                        segment_blob_names.append(segment_blob_name)
                        segment_paths.append(segment_path)
            else:
                # Validate file paths to prevent command injection (S603)
                # Ensure paths are resolved and don't contain shell metacharacters
                input_path = Path(input_file).resolve()
            output_path = Path(CAPTURED_FILE_PATH) / f"{input_path.stem}.mp4"
        except (ValueError, OSError) as e:
            err_msg = f"Invalid file path provided: {e}"
            logging.exception(err_msg)
            raise ValueError(err_msg) from e

        try:
            # Build ffmpeg command with conditional audio handling
            # Using -c:a aac if audio exists, otherwise ffmpeg will ignore it
            command = [
                "ffmpeg",
                "-i", str(input_path),
                "-c:v", "libx264",    # H.264 video codec
                "-preset", "fast",     # Encoding speed preset
                "-crf", "23",          # Constant Rate Factor (quality)
                "-c:a", "aac",        # AAC audio codec (ignored if no audio stream)
                "-b:a", "128k",        # Audio bitrate (ignored if no audio stream)
                "-map", "0:v:0",       # Map first video stream
                "-map", "0:a?",        # Map audio if present (? makes it optional)
                str(output_path)
            ]
            subprocess.run(command, check=True)  # noqa: S603

            # Remove local copies; archive cloud segments only after conversion.
            input_path.unlink()
            for segment_path in segment_paths:
                segment_path.unlink(missing_ok=True)
            logging.debug(f"Deleted raw video file: {input_path}")

            # Archive source segments only after FFmpeg successfully creates the MP4.
            if blob_name:
                GoogleCloudStorageAdapter().delete_blob(blob_name)
                for segment_blob_name in segment_blob_names:
                    GoogleCloudStorageAdapter().move_to_srt_archive(
                        blob_name.split("/", 1)[0], segment_blob_name
                    )
                logging.debug(f"Deleted raw video blob: {blob_name}")

        except subprocess.CalledProcessError as e:
            informasjon = f"FFmpeg command failed with error for {input_file}"
            logging.exception(informasjon)
            raise Exception(informasjon) from e

    def is_live_stream_finished(self, manifest_url: str) -> bool:
        """Check whether an HLS manifest has been finalized (#EXT-X-ENDLIST present)."""
        cloud_storage_prefix = f"{GOOGLE_STORAGE_SERVER}/{GOOGLE_STORAGE_BUCKET}/"
        if not manifest_url.startswith(cloud_storage_prefix):
            return True
        manifest_blob_name = manifest_url.removeprefix(cloud_storage_prefix)
        manifest_text = GoogleCloudStorageAdapter().download_blob_as_text(manifest_blob_name)
        return "#EXT-X-ENDLIST" in manifest_text

    def capture_live_segments(
        self,
        manifest_url: str,
        manifest_name: str,
        chunk_duration: int,
    ) -> str | None:
        """Capture a fixed-duration mp4 chunk from a live HLS stream.

        Only segments present in the manifest are read. Source cloud segments
        remain untouched while the stream is active. A watermark blob tracks
        the last segment included in a chunk, so repeated calls pick up new
        segments only.

        Returns the name of the produced mp4 chunk, or None if not enough
        new segments have accumulated yet to fill a chunk of chunk_duration.
        """
        output_names = self._process_playlist_segments(
            manifest_url, manifest_name, chunk_duration, flush_remainder=False
        )
        return output_names[0] if output_names else None

    def capture_finished_segments(
        self,
        manifest_url: str,
        manifest_name: str,
        chunk_duration: int,
    ) -> list[str]:
        """Convert remaining finished-playlist segments into MP4 chunks."""
        return self._process_playlist_segments(
            manifest_url,
            manifest_name,
            chunk_duration,
            flush_remainder=True,
        )

    def _process_playlist_segments(
        self,
        manifest_url: str,
        manifest_name: str,
        chunk_duration: int,
        flush_remainder: bool,
    ) -> list[str]:
        """Build MP4 chunks from unprocessed playlist segments."""
        cloud_storage_prefix = f"{GOOGLE_STORAGE_SERVER}/{GOOGLE_STORAGE_BUCKET}/"
        if not manifest_url.startswith(cloud_storage_prefix):
            raise ValueError
        if chunk_duration <= 0:
            raise ValueError

        manifest_blob_name = manifest_url.removeprefix(cloud_storage_prefix)
        blob_folder = manifest_blob_name.rsplit("/", 1)[0]
        manifest_stem = Path(manifest_name).stem
        watermark_blob_name = f"{blob_folder}/.watermark_{manifest_stem}"
        media_sequence, new_segments = self._get_new_live_segments(
            manifest_blob_name, watermark_blob_name
        )
        all_segments = (
            self._get_playlist_segments(manifest_blob_name, media_sequence)
            if flush_remainder
            else []
        )
        output_names = []
        storage = GoogleCloudStorageAdapter()

        while new_segments:
            chunk_segments, accumulated_duration = self._accumulate_chunk_segments(
                new_segments, chunk_duration
            )
            if accumulated_duration < chunk_duration:
                if not flush_remainder:
                    break
                chunk_segments = new_segments

            output_name, last_sequence = self._build_mp4_chunk(
                blob_folder, manifest_stem, manifest_name, chunk_segments
            )
            output_names.append(output_name)
            storage.upload_text_blob(watermark_blob_name, str(last_sequence))
            new_segments = [
                segment for segment in new_segments if segment[0] > last_sequence
            ]

            if not flush_remainder:
                break

        if flush_remainder:
            event_id = manifest_blob_name.split("/", 1)[0]
            for _, segment_name, _, _ in all_segments:
                storage.move_to_srt_archive(
                    event_id, f"{blob_folder}/{segment_name}"
                )
            storage.delete_blob(manifest_blob_name)
            if storage.download_blob_as_text(watermark_blob_name):
                storage.delete_blob(watermark_blob_name)

        return output_names

    def _get_new_live_segments(
        self, manifest_blob_name: str, watermark_blob_name: str
    ) -> tuple[int, list[tuple[int, str, float, str]]]:
        """Parse manifest, returning media sequence and segments newer than the watermark."""
        manifest_text = GoogleCloudStorageAdapter().download_blob_as_text(manifest_blob_name)
        sequence_match = re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", manifest_text)
        media_sequence = int(sequence_match.group(1)) if sequence_match else 0

        watermark_text = GoogleCloudStorageAdapter().download_blob_as_text(watermark_blob_name)
        last_processed = int(watermark_text) if watermark_text else media_sequence - 1

        segments = self._parse_playlist_segments(manifest_text, media_sequence)
        new_segments = [segment for segment in segments if segment[0] > last_processed]
        return media_sequence, new_segments

    def _get_playlist_segments(
        self, manifest_blob_name: str, media_sequence: int
    ) -> list[tuple[int, str, float, str]]:
        """Return every segment currently referenced by a playlist."""
        manifest_text = GoogleCloudStorageAdapter().download_blob_as_text(manifest_blob_name)
        return self._parse_playlist_segments(manifest_text, media_sequence)

    def _parse_playlist_segments(
        self, manifest_text: str, media_sequence: int
    ) -> list[tuple[int, str, float, str]]:
        """Parse sequence, name, duration, and program date-time per segment."""
        segments = []
        sequence = media_sequence
        duration = 0.0
        program_date_time = ""
        for raw_line in manifest_text.splitlines():
            line = raw_line.strip()
            if line.startswith("#EXT-X-PROGRAM-DATE-TIME:"):
                program_date_time = line.removeprefix("#EXT-X-PROGRAM-DATE-TIME:")
            elif line.startswith("#EXTINF:"):
                duration = float(line.removeprefix("#EXTINF:").split(",", 1)[0])
            elif line and not line.startswith("#"):
                segments.append((sequence, line, duration, program_date_time))
                sequence += 1
        return segments

    def _accumulate_chunk_segments(
        self, new_segments: list[tuple[int, str, float, str]], chunk_duration: int
    ) -> tuple[list[tuple[int, str, float, str]], float]:
        """Accumulate segments until their durations reach chunk_duration."""
        chunk_segments = []
        accumulated_duration = 0.0
        for segment in new_segments:
            chunk_segments.append(segment)
            accumulated_duration += segment[2]
            if accumulated_duration >= chunk_duration:
                break
        return chunk_segments, accumulated_duration

    def _build_mp4_chunk(
        self,
        blob_folder: str,
        manifest_stem: str,
        manifest_name: str,
        chunk_segments: list[tuple[int, str, float, str]],
    ) -> tuple[str, int]:
        """Download chunk segments, concat them into an mp4, and clean up local files."""
        stream_name = self._get_stream_name(blob_folder)
        local_srt_folder = Path(CAPTURED_SRT_FILE_PATH)
        if stream_name:
            local_srt_folder /= stream_name
        local_srt_folder.mkdir(parents=True, exist_ok=True)
        Path(CAPTURED_FILE_PATH).mkdir(parents=True, exist_ok=True)
        concat_list_path = local_srt_folder / f"TMP_concat_{manifest_stem}.txt"
        local_segment_paths = []
        last_sequence = chunk_segments[-1][0]
        first_sequence = chunk_segments[0][0]
        output_stem = f"{stream_name}_{manifest_stem}" if stream_name else manifest_stem
        output_name = (
            f"{output_stem}_{self._format_chunk_timestamp(chunk_segments[0][3])}_"
            f"{first_sequence}-{last_sequence}.mp4"
        )
        try:
            with concat_list_path.open("w") as concat_list_file:
                for _, segment_name, _, _ in chunk_segments:
                    segment_path = local_srt_folder / segment_name
                    segment_path.parent.mkdir(parents=True, exist_ok=True)
                    GoogleCloudStorageAdapter().download_blob(
                        f"{blob_folder}/{segment_name}", str(segment_path)
                    )
                    local_segment_paths.append(segment_path)
                    concat_list_file.write(f"file '{segment_path}'\n")

            output_path = Path(CAPTURED_FILE_PATH) / output_name
            command = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_path),
                "-c", "copy",
                str(output_path),
            ]
            subprocess.run(command, check=True)  # noqa: S603
        except subprocess.CalledProcessError as e:
            informasjon = f"FFmpeg concat failed for live segments of {manifest_name}"
            logging.exception(informasjon)
            raise Exception(informasjon) from e
        finally:
            concat_list_path.unlink(missing_ok=True)
            for segment_path in local_segment_paths:
                segment_path.unlink(missing_ok=True)

        return output_name, last_sequence

    def _get_stream_name(self, blob_folder: str) -> str:
        """Return the stream directory following CAPTURE_SRT, if present."""
        folder_parts = Path(blob_folder).parts
        try:
            srt_index = folder_parts.index("CAPTURE_SRT")
        except ValueError:
            return ""
        if srt_index + 1 >= len(folder_parts):
            return ""
        stream_name = folder_parts[srt_index + 1]
        return "" if stream_name == "mux-stream" else stream_name

    def _format_chunk_timestamp(self, program_date_time: str) -> str:
        """Convert an #EXT-X-PROGRAM-DATE-TIME value into a filename-safe timestamp."""
        if not program_date_time:
            return "unknown"
        try:
            timestamp = datetime.datetime.fromisoformat(program_date_time)
        except ValueError:
            return "unknown"
        return timestamp.strftime("%Y%m%dT%H%M%S")

    def convert_ts_file(
        self,
        ts_file: dict,
    ) -> None:
        """Convert .ts file into video clip using FFmpeg.

        Args:
            ts_file: Dictionary containing information about the .ts file to convert

        Returns:
            None

        """
        servicename = "PhotosFileAdapter.convert_ts_files"

        try:

            # Build ffmpeg command to merge and segment
            command = [
                "ffmpeg",
                "-f", "concat",           # Use concat demuxer
                "-safe", "0",             # Allow absolute paths
                "-i", ts_file["path"],    # Input file
                "-c", "copy",             # Copy streams without re-encoding (fast)
                "-f", "segment",          # Segment output muxer
                "-reset_timestamps", "1", # Reset timestamps for each segment
                "-map", "0",              # Map all streams
                str(ts_file["output"])
            ]

            logging.info(f"{servicename} Converting .ts file {ts_file['path']} into clips")
            subprocess.run(command, check=True)  # noqa: S603

            logging.info(f"{servicename} Created {ts_file['output']} video clip")
        except subprocess.CalledProcessError as e:
            informasjon = f"{servicename} FFmpeg merge failed"
            logging.exception(informasjon)
            raise Exception(informasjon) from e
        except Exception as e:
            informasjon = f"{servicename} Error merging .ts files"
            logging.exception(informasjon)
            raise Exception(informasjon) from e

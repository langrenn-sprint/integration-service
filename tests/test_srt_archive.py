"""Tests for archiving SRT video segments."""

from pathlib import Path
from unittest.mock import Mock, patch

from integration_service.adapters import (
    google_cloud_storage_adapter,
    photos_file_adapter,
)


def test_move_to_srt_archive_preserves_source_path() -> None:
    """Archive a segment without flattening its source path."""
    adapter = google_cloud_storage_adapter.GoogleCloudStorageAdapter()
    with patch.object(adapter, "move_blob", return_value="archive-url") as move_blob:
        result = adapter.move_to_srt_archive(
            "event-1", "event-1/CAPTURE_SRT/mux-stream/segment-1.ts"
        )

    assert result == "archive-url"
    move_blob.assert_called_once_with(
        "event-1/CAPTURE_SRT/mux-stream/segment-1.ts",
        "event-1/CAPTURE_SRT/archive/mux-stream/segment-1.ts",
    )


def test_convert_raw_to_mp4_archives_segments_after_ffmpeg(tmp_path: Path) -> None:
    """Move cloud segments only once the playlist conversion succeeds."""
    events = []
    srt_path = tmp_path / "CAPTURE_SRT"
    capture_path = tmp_path / "CAPTURE"
    storage = Mock()

    def download_blob(blob_name: str, destination: str) -> None:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            "#EXTM3U\nsegment-1.ts\n"
            if blob_name.endswith(".m3u8")
            else "segment data"
        )

    storage.download_blob.side_effect = download_blob
    storage.move_to_srt_archive.side_effect = lambda *_: events.append("archive")

    with (
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_SERVER", "https://storage.test"),
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_BUCKET", "bucket"),
        patch.object(photos_file_adapter, "CAPTURED_SRT_FILE_PATH", str(srt_path)),
        patch.object(photos_file_adapter, "CAPTURED_FILE_PATH", str(capture_path)),
        patch.object(photos_file_adapter, "GoogleCloudStorageAdapter", return_value=storage),
        patch.object(
            photos_file_adapter.subprocess,
            "run",
            side_effect=lambda *_args, **_kwargs: events.append("ffmpeg"),
        ),
    ):
        photos_file_adapter.PhotosFileAdapter().convert_raw_to_mp4(
            "https://storage.test/bucket/event-1/CAPTURE_SRT/mux-stream/playlist.m3u8"
        )

    assert events == ["ffmpeg", "archive"]
    storage.move_to_srt_archive.assert_called_once_with(
        "event-1", "event-1/CAPTURE_SRT/mux-stream/segment-1.ts"
    )
    storage.delete_blob.assert_called_once_with(
        "event-1/CAPTURE_SRT/mux-stream/playlist.m3u8"
    )


def test_capture_live_segments_leaves_source_segments_in_place() -> None:
    """Do not archive or delete segments until the stream has finished."""
    adapter = photos_file_adapter.PhotosFileAdapter()
    segments = [(10, "segment-10.ts", 2.0, ""), (11, "segment-11.ts", 2.0, "")]
    storage = Mock()

    with (
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_SERVER", "https://storage.test"),
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_BUCKET", "bucket"),
        patch.object(adapter, "_get_new_live_segments", return_value=(10, segments)),
        patch.object(adapter, "_build_mp4_chunk", return_value=("chunk.mp4", 11)),
        patch.object(photos_file_adapter, "GoogleCloudStorageAdapter", return_value=storage),
    ):
        result = adapter.capture_live_segments(
            "https://storage.test/bucket/event-1/CAPTURE_SRT/mux-stream/live.m3u8",
            "live.m3u8",
            4,
        )

    assert result == "chunk.mp4"
    storage.move_to_srt_archive.assert_not_called()
    storage.delete_blob.assert_not_called()


def test_capture_finished_segments_chunks_and_flushes_remainder() -> None:
    """Build full-duration chunks and a final shorter chunk for a finished stream."""
    adapter = photos_file_adapter.PhotosFileAdapter()
    segments = [
        (7, "segment-7.ts", 6.0, ""),
        (8, "segment-8.ts", 4.0, ""),
        (9, "segment-9.ts", 4.0, ""),
        (10, "segment-10.ts", 1.0, ""),
    ]
    storage = Mock()
    storage.download_blob_as_text.return_value = "10"

    def build_chunk(_folder: str, _stem: str, _name: str, chunk_segments: list) -> tuple[str, int]:
        first_sequence = chunk_segments[0][0]
        last_sequence = chunk_segments[-1][0]
        return f"playlist_{first_sequence}-{last_sequence}.mp4", last_sequence

    with (
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_SERVER", "https://storage.test"),
        patch.object(photos_file_adapter, "GOOGLE_STORAGE_BUCKET", "bucket"),
        patch.object(
            adapter,
            "_get_new_live_segments",
            return_value=(7, segments),
        ),
        patch.object(adapter, "_get_playlist_segments", return_value=segments),
        patch.object(adapter, "_build_mp4_chunk", side_effect=build_chunk) as build,
        patch.object(photos_file_adapter, "GoogleCloudStorageAdapter", return_value=storage),
    ):
        results = adapter.capture_finished_segments(
            "https://storage.test/bucket/event-1/CAPTURE_SRT/mux-stream/playlist.m3u8",
            "playlist.m3u8",
            10,
        )

    assert results == ["playlist_7-8.mp4", "playlist_9-10.mp4"]
    assert [call.args[3] for call in build.call_args_list] == [segments[:2], segments[2:]]
    assert [call.args[1] for call in storage.upload_text_blob.call_args_list] == ["8", "10"]
    assert storage.move_to_srt_archive.call_count == len(segments)
    storage.delete_blob.assert_any_call(
        "event-1/CAPTURE_SRT/mux-stream/playlist.m3u8"
    )
    storage.delete_blob.assert_any_call(
        "event-1/CAPTURE_SRT/mux-stream/.watermark_playlist"
    )


def test_build_mp4_chunk_names_without_timestamp_are_unique(tmp_path: Path) -> None:
    """Use segment sequence ranges to distinguish chunks without timestamps."""
    adapter = photos_file_adapter.PhotosFileAdapter()
    storage = Mock()

    def download_blob(_blob_name: str, destination: str) -> None:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text("segment data")

    storage.download_blob.side_effect = download_blob
    chunks = [
        [(30, "segment-30.ts", 5.0, ""), (31, "segment-31.ts", 5.0, "")],
        [(32, "segment-32.ts", 5.0, ""), (33, "segment-33.ts", 5.0, "")],
    ]

    with (
        patch.object(photos_file_adapter, "CAPTURED_SRT_FILE_PATH", str(tmp_path / "srt")),
        patch.object(photos_file_adapter, "CAPTURED_FILE_PATH", str(tmp_path / "capture")),
        patch.object(photos_file_adapter, "GoogleCloudStorageAdapter", return_value=storage),
        patch.object(photos_file_adapter.subprocess, "run"),
    ):
        names = [
            adapter._build_mp4_chunk(  # noqa: SLF001
                "event/mux-stream", "playlist", "playlist.m3u8", chunk
            )[0]
            for chunk in chunks
        ]

    assert names == ["playlist_unknown_30-31.mp4", "playlist_unknown_32-33.mp4"]


def test_build_mp4_chunk_names_and_temp_files_include_stream(tmp_path: Path) -> None:
    """Keep same-named playlists and segments isolated between streams."""
    adapter = photos_file_adapter.PhotosFileAdapter()
    storage = Mock()

    def download_blob(_blob_name: str, destination: str) -> None:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text("segment data")

    storage.download_blob.side_effect = download_blob
    chunk = [(30, "segment-30.ts", 5.0, "")]

    with (
        patch.object(photos_file_adapter, "CAPTURED_SRT_FILE_PATH", str(tmp_path / "srt")),
        patch.object(photos_file_adapter, "CAPTURED_FILE_PATH", str(tmp_path / "capture")),
        patch.object(photos_file_adapter, "GoogleCloudStorageAdapter", return_value=storage),
        patch.object(photos_file_adapter.subprocess, "run") as run_ffmpeg,
    ):
        names = [
            adapter._build_mp4_chunk(  # noqa: SLF001
                f"event/CAPTURE_SRT/{stream}/mux-stream",
                "playlist",
                "playlist.m3u8",
                chunk,
            )[0]
            for stream in ("tir1", "tir2")
        ]

    assert names == [
        "tir1_playlist_unknown_30-30.mp4",
        "tir2_playlist_unknown_30-30.mp4",
    ]
    downloaded_paths = [Path(call.args[1]) for call in storage.download_blob.call_args_list]
    assert downloaded_paths == [
        tmp_path / "srt/tir1/segment-30.ts",
        tmp_path / "srt/tir2/segment-30.ts",
    ]
    output_paths = [Path(call.args[0][-1]) for call in run_ffmpeg.call_args_list]
    assert output_paths == [
        tmp_path / "capture/tir1_playlist_unknown_30-30.mp4",
        tmp_path / "capture/tir2_playlist_unknown_30-30.mp4",
    ]

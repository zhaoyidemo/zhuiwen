"""视频处理：从视频 URL 截取前 N 秒的关键帧"""
import asyncio
import base64
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


async def extract_first_frames(video_url: str, seconds: int = 5, fps: int = 1) -> list[str]:
    """
    用 ffmpeg 截取视频前 N 秒的帧，返回 base64 JPEG 列表。

    Args:
        video_url: 视频直链（抖音 CDN）
        seconds: 截取秒数，默认 5
        fps: 每秒截取帧数，默认 1

    Returns:
        base64 编码的 JPEG 图片列表（data URI 格式）
    """
    tmpdir = tempfile.mkdtemp(prefix="zhuiwen_frames_")
    pattern = os.path.join(tmpdir, "frame_%02d.jpg")

    cmd = [
        "ffmpeg",
        "-i", video_url,
        "-t", str(seconds),
        "-vf", f"fps={fps}",
        "-frames:v", str(seconds * fps + 1),
        "-q:v", "3",        # JPEG 质量（2=最佳, 31=最差）
        "-vframes", str(seconds * fps + 1),
        pattern,
        "-y",                # 覆盖已有文件
        "-loglevel", "warning",
    ]

    logger.info(f"截帧命令: ffmpeg -i <video_url> -t {seconds} -vf fps={fps} ...")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"ffmpeg 截帧失败 (code={proc.returncode}): {err_msg}")
            return []

        # 读取生成的帧文件
        frames = []
        for i in range(1, seconds * fps + 2):
            path = os.path.join(tmpdir, f"frame_{i:02d}.jpg")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                    frames.append(f"data:image/jpeg;base64,{b64}")

        logger.info(f"截帧成功: {len(frames)} 帧")
        return frames

    except asyncio.TimeoutError:
        logger.error("ffmpeg 截帧超时（30秒）")
        return []
    except FileNotFoundError:
        logger.error("ffmpeg 未安装，请确认 nixpacks.toml 配置了 aptPkgs = [\"ffmpeg\"]")
        return []
    finally:
        # 清理临时文件
        try:
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)
        except Exception:
            pass

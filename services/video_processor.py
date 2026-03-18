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
    """
    tmpdir = tempfile.mkdtemp(prefix="zhuiwen_frames_")
    pattern = os.path.join(tmpdir, "frame_%02d.jpg")
    max_frames = seconds * fps + 1

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "warning",
        "-i", video_url,
        "-t", str(seconds),
        "-vf", f"fps={fps}",
        "-frames:v", str(max_frames),
        "-q:v", "3",
        pattern,
    ]

    logger.info(f"截帧开始: seconds={seconds}, fps={fps}, max_frames={max_frames}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.info(f"ffmpeg stderr: {stderr_text[:500]}")

        if proc.returncode != 0:
            logger.error(f"ffmpeg 截帧失败 (code={proc.returncode}): {stderr_text}")
            return []

        # 读取生成的帧文件
        frames = []
        for i in range(1, max_frames + 1):
            path = os.path.join(tmpdir, f"frame_{i:02d}.jpg")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                    frames.append(f"data:image/jpeg;base64,{b64}")

        logger.info(f"截帧完成: {len(frames)} 帧")
        return frames

    except asyncio.TimeoutError:
        logger.error("ffmpeg 截帧超时（60秒）")
        return []
    except FileNotFoundError:
        logger.error("ffmpeg 未安装")
        return []
    except Exception as e:
        logger.error(f"截帧异常: {type(e).__name__}: {e}")
        return []
    finally:
        try:
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)
        except Exception:
            pass

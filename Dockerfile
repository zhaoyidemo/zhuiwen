# Stage 1: 构建前端
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# Stage 2: 运行后端 + 服务前端静态文件
FROM python:3.12-slim
WORKDIR /app

# 安装后端依赖
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# 暴露端口
EXPOSE 8000

# 启动（Railway 通过 PORT 环境变量传入端口）
CMD python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}

module.exports = {
  apps: [
    {
      name: "mister-reposter",
      script: "main.py",
      interpreter: "python3",
      watch: false,
      max_memory_restart: "250M",
      env: {
        NODE_ENV: "production",
        PYTHONUNBUFFERED: "1"
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/pm2_error.log",
      out_file: "logs/pm2_out.log",
      merge_logs: true,
      autorestart: true,
      restart_delay: 5000
    }
  ]
};

const { spawn } = require("child_process");
const path = require("path");

const electronBin = path.join(__dirname, "..", "node_modules", ".bin",
  process.platform === "win32" ? "electron.cmd" : "electron"
);

const p = spawn(electronBin, [path.join(__dirname, "..")], { stdio: "inherit" });
p.on("exit", (code) => process.exit(code ?? 0));

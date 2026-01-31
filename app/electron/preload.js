const { contextBridge } = require("electron");
contextBridge.exposeInMainWorld("aurora", { version: "0.1.0" });

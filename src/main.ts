import "leaflet/dist/leaflet.css";
import "./styles/app.css";
import { marked } from "marked";
import { AppController } from "./lib/app-controller";

marked.setOptions({
  gfm: true,
  breaks: true
});

const mount = document.querySelector<HTMLDivElement>("#app");

if (!mount) {
  throw new Error("App mount element not found.");
}

const app = new AppController(mount);
app.start().catch((error) => {
  console.error(error);
  mount.innerHTML = `<main class="fatal-error"><h1>Application failed to start</h1><p>${String(error)}</p></main>`;
});


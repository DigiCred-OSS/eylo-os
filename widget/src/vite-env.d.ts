/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SERVER_BASE_HOST: string;
  readonly VITE_SERVER_BASE_PORT: string;
  readonly VITE_SERVER_WS_BASE_URL: string;
  readonly VITE_SERVER_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

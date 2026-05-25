# Vendored browser assets

The React UI is intentionally served without a Node build step. To keep local and deployed environments independent of CDN access, these browser runtimes are vendored under `static/vendor/`.

- React UMD runtime: https://github.com/facebook/react, MIT License.
- ReactDOM UMD runtime: https://github.com/facebook/react, MIT License.
- Lucide UMD runtime: https://github.com/lucide-icons/lucide, ISC License.

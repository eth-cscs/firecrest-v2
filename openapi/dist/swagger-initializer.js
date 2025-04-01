window.onload = function() {
  //<editor-fold desc="Changeable Configuration Block">

  // the following lines will be replaced by docker/configurator, when it runs in a docker-container
  window.ui = SwaggerUIBundle({
    urls: [
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-latest.yaml", name: "Latest"},
      //add-newones-here
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-master.yaml", name: "master"},
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-2.2.3.yaml", name: "2.2.3"},
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-2.2.3.yaml", name: "2.2.3"},
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-2.2.2.yaml", name: "2.2.2"},
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-2.2.1.yaml", name: "2.2.1"},
      {url: "https://eth-cscs.github.io/firecrest-v2/openapi/openapi-v2.2.0.yaml", name: "2.2.0"}
    ],
    "urls.primaryName": "Latest",
    dom_id: '#swagger-ui',
    deepLinking: true,
    presets: [
      SwaggerUIBundle.presets.apis,
      SwaggerUIStandalonePreset
    ],
    plugins: [
      SwaggerUIBundle.plugins.DownloadUrl
    ],
    layout: "StandaloneLayout"
  });

  //</editor-fold>
};



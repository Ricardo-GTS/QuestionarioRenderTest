// Formularios de questao (criar e editar no admin): mostra "Novo topico" so' quando
// escolhido e conta os caracteres do enunciado. Delegacao no document + reaplica depois
// de cada troca do HTMX (o formulario volta do servidor com erro ou questao parecida;
// script inline no fragmento roda antes do fragmento estar no lugar).
(function () {
  function sync() {
    document.querySelectorAll("[data-new-topic-value]").forEach(function (wrapper) {
      var form = wrapper.closest("form");
      var topic = form && form.querySelector('select[name="topic"]');
      if (topic) wrapper.hidden = topic.value !== wrapper.dataset.newTopicValue;
    });
    var statement = document.getElementById("id_statement");
    var count = document.getElementById("statement-count");
    if (statement && count) count.textContent = statement.value.length + " caracteres";
  }
  document.addEventListener("change", function (event) {
    if (event.target.name === "topic") sync();
  });
  document.addEventListener("input", function (event) {
    if (event.target.id === "id_statement") sync();
  });
  document.addEventListener("htmx:afterSettle", sync);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", sync);
  else sync();
})();

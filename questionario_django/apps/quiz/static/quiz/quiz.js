// Atalhos do Treinar (computador): V e F respondem, Enter vai para a proxima.
// Delegacao no document: continua funcionando depois das trocas de card do HTMX.
// Ignorado quando o foco esta num campo (comentario, reporte, escolher topicos).
(function () {
  document.addEventListener("keydown", function (event) {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    var target = event.target;
    if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
    var card = document.getElementById("quiz-card");
    if (!card) return;
    var key = event.key.toLowerCase();
    var wanted = key === "v" ? "v" : key === "f" ? "f" : key === "enter" ? "next" : null;
    if (!wanted) return;
    var button = card.querySelector('[data-key="' + wanted + '"]');
    if (!button || button.disabled) return;
    if (wanted === "next" && target && target.tagName === "BUTTON" && target !== button) return;
    event.preventDefault();
    button.click();
  });
})();

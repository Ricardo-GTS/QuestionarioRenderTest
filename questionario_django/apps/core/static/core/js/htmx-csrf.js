// Anexa o token CSRF a toda requisicao disparada pelo HTMX.
// Unico script de "infraestrutura" do projeto -- nao e' logica de aplicacao.
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

document.body.addEventListener("htmx:configRequest", (event) => {
  event.detail.headers["X-CSRFToken"] = getCookie("csrftoken");
});

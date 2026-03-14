document.addEventListener("click", function(e){

    const btn = e.target.closest(".add-to-cart-btn");

    if(!btn) return;

    e.preventDefault();

    if(btn.classList.contains("loading")) return;

    btn.classList.add("loading");

    const productId = btn.dataset.id;

    fetch(`/add-to-cart/${productId}/`)
    .then(res => res.json())
    .then(data => {

        if(data.success){

            const cartCounter = document.querySelector("#cart-count");

            if(cartCounter){
                cartCounter.textContent = data.cart_count;
            }

        }

    })
    .catch(err => console.error(err))
    .finally(() => {
        btn.classList.remove("loading");
    });

});
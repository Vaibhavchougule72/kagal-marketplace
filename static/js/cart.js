document.addEventListener("click", function(e){

    // PRODUCT ADD
    if(e.target.classList.contains("add-to-cart-btn")){

        const productId = e.target.dataset.id

        fetch(`/add-to-cart/${productId}/`)
        .then(res => res.json())
        .then(data => {

            if(data.success){

                const badge = document.getElementById("cart-count")

                if(badge){
                    badge.innerText = data.cart_count
                }

            }

        })

    }

    // BUNDLE ADD
    if(e.target.classList.contains("add-bundle-btn")){

        const bundleId = e.target.dataset.id

        fetch(`/add-bundle-to-cart/${bundleId}/`)
        .then(res => res.json())
        .then(data => {

            if(data.success){

                const badge = document.getElementById("cart-count")

                if(badge){
                    badge.innerText = data.cart_count
                }

            }

        })

    }

})
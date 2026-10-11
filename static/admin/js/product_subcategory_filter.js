document.addEventListener("DOMContentLoaded", function () {
    const categoryField = document.getElementById("id_category");
    const subcategoryField = document.getElementById("id_subcategory");

    if (!categoryField || !subcategoryField) {
        return;
    }

    // Save the currently selected subcategory.
    let previousCategory = categoryField.value;

    categoryField.addEventListener("change", function () {
        const categoryId = categoryField.value;

        // Clear the subcategory when the category changes.
        subcategoryField.value = "";

        if (!categoryId) {
            subcategoryField.innerHTML = '<option value="">---------</option>';
            previousCategory = categoryId;
            return;
        }

        // Fetch subcategories from the admin endpoint.
        fetch(
            `/admin/product-subcategories/?category_id=${encodeURIComponent(categoryId)}`,
            {
                headers: {
                    "X-Requested-With": "XMLHttpRequest"
                }
            }
        )
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Unable to load subcategories.");
                }
                return response.json();
            })
            .then(function (data) {
                subcategoryField.innerHTML =
                    '<option value="">---------</option>';

                data.subcategories.forEach(function (item) {
                    const option = document.createElement("option");
                    option.value = item.id;
                    option.textContent = item.name;
                    subcategoryField.appendChild(option);
                });

                previousCategory = categoryId;
            })
            .catch(function (error) {
                console.error(error);
            });
    });
});
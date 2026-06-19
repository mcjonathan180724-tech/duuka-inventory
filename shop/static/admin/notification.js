document.addEventListener(
    'click',
    function (e) {

        const link =
            e.target.closest(
                '.notification-link'
            );

        if (!link) return;

        e.preventDefault();

        const id =
            link.dataset.id;

        console.log(
            'clicked',
            id
        );

        fetch(
            `/admin/shop/notification/${id}/popup/`
        )

        .then(response =>
            response.json()
        )

        .then(data => {

            alert(data.message);

            location.reload();
        })

        .catch(error => {

            console.error(
                error
            );
        });
});
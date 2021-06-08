$(document).ready(function() {
    $('#submit_key').submit(function (e) {

        e.preventDefault();

        $.ajax({
            type: "POST",
            url: "/poloniex/balance/",
            data: $('#submit_key').serialize(),

            success: function (data) {
                console.log('Submission was successful.');
                console.log(data);
            }
        });
    });
});
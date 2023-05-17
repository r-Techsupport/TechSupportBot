// This is the javascript that turns the application google form into a json and sends it to discord via a webhook

const POST_URL = "";

function onSubmit(e) {
    var form = FormApp.getActiveForm();
    var allResponses = form.getResponses();
    var latestResponse = allResponses[allResponses.length - 1];
    var response = latestResponse.getItemResponses();
    var items = [];
    var fullUsername = "";

    for (var i = 0; i < response.length; i++) {
        var question = response[i].getItem().getTitle();
        var answer = response[i].getResponse();
        try {
            var parts = answer.match(/[\s\S]{1,1024}/g) || [];
        } catch (e) {
            var parts = answer;
        }

        if (answer == "") {
            continue;
        }

        if (i == 0) {
          fullUsername = parts[0];
        }

        for (var j = 0; j < parts.length; j++) {
            if (j == 0) {
                items.push({
                    "question": question,
                    "answer": parts[j],
                });
            } else {
                items.push({
                    "question": question.concat(" (cont.)"),
                    "answer": parts[j],
                });
            }
        }
    }

    var payloadContent = {
      "responses": items,
      "username": fullUsername
    }

    var options = {
        "method": "post",
        "headers": {
            "Content-Type": "application/json",
        },
        "payload": JSON.stringify({
            "content": JSON.stringify(payloadContent),
            "embeds": []
        })
    };

    UrlFetchApp.fetch(POST_URL, options);
};

dictionary = {
    "name": "Name",
    "frequency": "Frequency",
    "effect": "Effect",
    "trigger": "Trigger",
    "bonus": "Bonus",
    "special": "Special",
    "type": "Type",
    "ac": "AC",
    "damage_base": "Damage Base",
    "class": "Class",
    "range": "Range",
    "contest_type": "Contest Type",
    "contest_effect": "Contest Effect",
    "set_up_effect": "Set-Up Effect",
    "resolution_effect": "Resolution Effect",
}

function replaceStringsWithDictionary(inputString, dictionary) {
    let str = inputString;
    Object.keys(dictionary).forEach(key => {
        if (str == key) {
            str = dictionary[key];
        }
    });
    return str;
}


function loadJsonAsText(file, container) {
    console.log(container);
        $.getJSON(file, function(data) {
                if (!Array.isArray(data) || data.length === 0) {
                    alert(`Error: no data found in ${file}`);
                    return;
                }

                data.forEach(item => {
                    let str = '';
                    Object.keys(item).forEach(key => {
                        if (key == "frequency") {
                            str += `${item[key] !== undefined ? item[key] : ""}<br>`;
                        }
                        else if (key == "name") {
                            str += `<strong>${item[key] !== undefined ? item[key] : ""}</strong><br>`;
                        }
                        else {
                            const parsedKey = replaceStringsWithDictionary(key, dictionary);
                            str += `<strong>${parsedKey}</strong>: ${item[key] !== undefined ? item[key] : ""}<br>`;
                        }
                    });
                    //str = str.slice(0, -2); // Remove the trailing comma and space
                    //console.log(str);

                    //container.innerHTML += `<div class=".col-4">${str}</div>`;

                    container.innerHTML += `<div class="col-12 col-md-4"><div class="card h-100"><div class="card-body">${str}</div></div></div>`;
                });
        });
}

function loadJsonToTable(file, tableId) {
    $.getJSON(file, function(data) {
        if (!Array.isArray(data) || data.length === 0) {
            $(`#${tableId} tbody`).append('<tr><td colspan="100%">Aucune donnée</td></tr>');
            return;
        }

        // Obtenir toutes les clés uniques de tous les objets
        const allKeys = new Set();
        data.forEach(item => {
            Object.keys(item).forEach(key => allKeys.add(key));
        });
        const keysArray = Array.from(allKeys);
        console.log(data);
        console.log(keysArray);

        // Créer l'en-tête du tableau
        let theadHtml = "";
        keysArray.forEach(key => {
            theadHtml += `<th>${key}</th>`;
        });
        $(`#${tableId} thead tr`).html(theadHtml);

        // Créer les lignes du tableau
        data.forEach(item => {
            let rowHtml = "";
            keysArray.forEach(key => {
                rowHtml += `<td>${item[key] !== undefined ? item[key] : ""}</td>`;
            });
            $(`#${tableId} tbody`).append(`<tr>${rowHtml}</tr>`);
        });
    }).fail(function() {
        alert("Erreur lors du chargement du JSON.");
    });
}
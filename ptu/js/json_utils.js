function loadJsonAsCard(file, container) {
    $.getJSON(file, function (data) {
        if (!Array.isArray(data) || data.length === 0) {
            alert(`Error: no data found in ${file}`);
            return;
        }

        data.forEach(item => {
            let str = '';
            Object.keys(item).forEach(key => {
                if (key == "Name") {
                    str += `<h3>${item[key] !== undefined ? item[key] : ""}</h3>`;
                }
                else if (key == "Frequency" && 1==0) {
                    str += `${item[key] !== undefined ? item[key] : ""}<br>`;
                }
                else if (key == "Damage Base") {
                    if (item[key] !== undefined) {
                        const regex = /(Damage Base.*:) (.*)/;
                        const match = item[key].match(regex);
                        if (!match) {
                            console.log("Error: damage_base format is incorrect in item:", item);
                        }
                        else {
                            str += `<strong>${match[1]}</strong> ${match[2]}<br>`;
                        }
                    }
                }
                else {
                    str += `<strong>${key}</strong>: ${item[key] !== undefined ? item[key] : ""}<br>`;
                    str = str.replaceAll("\n", "<br>");
                }
            });
            
            const cardDiv = document.createElement('div');
            cardDiv.className = "col-12 col-md-4";
            cardDiv.innerHTML = `<div class="card h-100"><div class="card-body">${str}</div></div>`;
            container.appendChild(cardDiv);
        });
    });
}

function loadJsonToTable(file, tableId) {
    $.getJSON(file, function (data) {
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
    }).fail(function () {
        alert("Erreur lors du chargement du JSON.");
    });
}

function loadJsonAsText(url, container) {
  fetch(url)
    .then(res => res.json())
    .then(data => {
      container.innerText = JSON.stringify(data, null, 2);
    })
    .catch(err => {
      container.innerText = "Erreur lors du chargement.";
    });
}

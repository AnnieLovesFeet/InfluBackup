class Influencer {
	constructor(code, group) {
		this.code = code;
		this.group = group;
		this.firstName = '';
		this.lastName = '';
		this.instagram = '';
		this.profileImage = '';
	}

	async loadInfluencer(jsonPath = '../../influencers.json') {
		const response = await fetch(jsonPath);
		if (!response.ok) {
			throw new Error(`Nie udało się wczytać influencerek: ${response.status}`);
		}

		const influencers = await response.json();
		const data = influencers.find((influencer) => (
			influencer.code === this.code && influencer.group === this.group
		));

		if (!data) {
			throw new Error(`Nie znaleziono influencera: ${this.group}/${this.code}`);
		}

		Object.assign(this, data);
		return this;
    }

	escapeHtml(value) {
		return String(value).replace(/[&<>"']/g, (character) => ({
			'&': '&amp;',
			'<': '&lt;',
			'>': '&gt;',
			'"': '&quot;',
			"'": '&#039;'
		}[character]));
	}

	render(container = document.querySelector('#influencer')) {
		if (!container) {
			throw new Error('Nie znaleziono elementu #influencer.');
		}

		container.className = 'influencer-profile';

		const name = `${this.firstName} ${this.lastName}`.trim() || this.code;
		const username = this.instagram.replace(/^@/, '');
		const profileImageUrl = this.profileImage
			? (() => {
				const path = this.profileImage.replace(/^\.?\//, '');
				const prefix = window.location.pathname.includes('/influencers/') ? '../../' : './';
				return new URL(prefix + path, window.location.href).href;
			})()
			: '';
		const image = this.profileImage
			? `<img src="${this.escapeHtml(profileImageUrl)}" alt="Profile image of ${this.escapeHtml(name)}">`
			: '';
		const instagram = this.instagram
			? `<a href="https://instagram.com/${this.escapeHtml(username)}" target="_blank" rel="noopener noreferrer">INSTAGRAM</a>`
			: '';

		container.innerHTML = `
            <div class="path">
                <p>${this.group}/${this.code}
            </div>

			<div class="profile-content">
			    ${image}

                <div class="column">
                    <h1>${this.escapeHtml(this.code)}</h1>
                    <p>${this.escapeHtml(name)}</p>
                    ${instagram}
                </div>
            </div>
		`;

		return container;
	}
}

async function render(group, code) {
	try {
		const influencer = new Influencer(code, group);
		await influencer.loadInfluencer();
		influencer.render();
		return influencer;
	} catch (error) {
		const container = document.querySelector('#influencer');
		if (container) {
			container.textContent = error.message;
		}
	}
}